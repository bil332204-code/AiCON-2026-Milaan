"""Synthetic multi-credit and shared-credit scenarios; no provider or bank access."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import pytest
from PIL import Image
from sqlalchemy import select, func
from app.models import Allocation, Match
from conftest import fresh_batch, reconcile, register


def funding_case(env, auth, totals=('100',), payments=(('60', 0, 'PAYMENT-001'),), *, refund=False, complete=True, status='Successful', confirmed=True, run=True):
    client, _, _ = env
    batch = fresh_batch(client, auth)
    orders = []
    for index, total in enumerate(totals):
        response = client.post(f'/api/batches/{batch["id"]}/orders/item', headers=auth,
                    json={'order_ref':f'ORDER-{index}','customer_name':f'Synthetic Seller {index}', 'amount_due':total, 'account_id':'wallet'})
        assert response.status_code == 201, response.text
        batch = response.json()['batch']; orders.append(response.json()['order'])
    csv = 'posted_at,direction,amount,counterparty,transaction_id\n'+'\n'.join(
        f'2026-10-09T14:00,CREDIT,{amount},Synthetic Payer,{reference}' for amount, _, reference in payments)
    if refund: csv += f'\n2026-10-09T14:05,DEBIT,{payments[0][0]},Synthetic Refund,{payments[0][2]}'
    response = client.post(f'/api/batches/{batch["id"]}/statement', headers=auth,
        files={'file':('synthetic.csv',csv,'text/csv')},data={'expected_revision':batch['revision'],'account_id':'wallet',
        'coverage_start':'2026-10-09T08:00','coverage_end':'2026-10-09T20:00','complete':str(complete).lower(),'references_verified':'true'})
    assert response.status_code == 201, response.text
    batch = response.json()['batch']; statement = response.json()['statement']
    lines = client.get(f'/api/statements/{statement["id"]}/lines', headers=auth).json()['items']
    credits = {line['transaction_id']:line for line in lines if line['direction']=='CREDIT'}
    claims = []
    for index, (amount, owner, reference) in enumerate(payments):
        image=BytesIO();Image.new('RGB',(80,80),(index*45,80,120)).save(image,'JPEG')
        response = client.post(f'/api/batches/{batch["id"]}/claims', headers=auth,
            files={'file':(f'synthetic-{index}.jpg',image.getvalue(),'image/jpeg')},data={'expected_revision':batch['revision'],'order_id':orders[owner]['id']})
        assert response.status_code == 201, response.text
        batch, claim = response.json()['batch'], response.json()['claim']
        response = client.patch(f'/api/claims/{claim["id"]}',headers=auth,json={'expected_version':claim['version'],'confirmed':confirmed,
            'fields':{'is_payment_receipt':True,'amount_pkr':amount,'datetime_local':'2026-10-09T14:00','transaction_id':reference,'status_text':status}})
        assert response.status_code == 200, response.text
        claims.append(response.json()['claim'])
        batch = client.get(f'/api/batches/{batch["id"]}',headers=auth).json()
    if not run: return {'batch':batch,'items':[]},credits,claims
    result = reconcile(env, auth, batch['id'], 'synthetic-case-run')
    result['items'].sort(key=lambda row:row['order']['order_ref'])
    return result, credits, claims


def allocation_body(result, selections):
    return {'expected_revision':result['batch']['revision'],'confirmed_relationships':True,
            'reason':'Synthetic seller confirmed the payment purpose and all allocation shares',
            'orders':[{'match_id':result['items'][index]['id'],'expected_version':result['items'][index]['version'],
                       'parts':[{'statement_line_id':line['id'],'claim_id':claim['id'],'amount_pkr':amount} for line,claim,amount in parts]}
                      for index,parts in selections]}


def submit(env, auth, result, body, key='review-payment-001'):
    return env[0].post(f'/api/batches/{result["batch"]["id"]}/allocation-review',headers={**auth,'Idempotency-Key':key},json=body)


def test_split_payment_requires_explicit_review_then_funds_order(env, auth):
    result,lines,claims=funding_case(env,auth,payments=(('60',0,'PAYMENT-001'),('40',0,'PAYMENT-002')))
    match=result['items'][0]
    assert match['reason_code']=='SPLIT_PAYMENT' and match['final_status']=='review' and match['allocated_paisa']==0
    body=allocation_body(result,[(0,[(lines['PAYMENT-001'],claims[0],'60'),(lines['PAYMENT-002'],claims[1],'40')])])
    response=submit(env,auth,result,body)
    assert response.status_code==200,response.text
    assert response.json()['items'][0]['final_status']=='ship'
    assert response.json()['items'][0]['allocated_paisa']==10000
    saved=env[0].get(f'/api/batches/{result["batch"]["id"]}/results',headers=auth).json()['items'][0]
    assert saved['machine_verdict']=='review' and saved['reason_code']=='SPLIT_PAYMENT'
    assert len(saved['allocations'])==2 and saved['selected_line_id'] is None
    exported=env[0].get(f'/api/batches/{result["batch"]["id"]}/export.csv',headers=auth)
    assert 'allocation_parts' in exported.text and '100.00' in exported.text


def test_partial_funding_reserves_only_its_share_and_never_ships(env, auth):
    result,lines,claims=funding_case(env,auth)
    assert result['items'][0]['reason_code']=='UNDERPAYMENT'
    response=submit(env,auth,result,allocation_body(result,[(0,[(lines['PAYMENT-001'],claims[0],'60')])]))
    assert response.status_code==200,response.text
    item=response.json()['items'][0]
    assert item['final_status']=='review' and item['outstanding_paisa']==4000


def test_combined_payment_is_reviewed_atomically_and_released_by_legacy_hold(env, auth):
    result,lines,claims=funding_case(env,auth,totals=('100','50'),payments=(('150',0,'COMBINED-001'),))
    assert all(item['reason_code']=='COMBINED_PAYMENT' and item['final_status']=='review' for item in result['items'])
    body=allocation_body(result,[(0,[(lines['COMBINED-001'],claims[0],'100')]),(1,[(lines['COMBINED-001'],claims[0],'50')])])
    response=submit(env,auth,result,body)
    assert response.status_code==200,response.text
    assert all(item['final_status']=='ship' for item in response.json()['items'])
    with env[1].sessions() as db:
        assert db.scalar(select(func.sum(Allocation.amount_paisa)))==15000
        assert db.scalar(select(func.count()).select_from(Allocation))==2
    first=response.json()['items'][0]
    released=env[0].post(f'/api/matches/{first["match_id"]}/decision',headers=auth,
        json={'expected_version':first['version'],'decision':'hold','reason':'Synthetic seller releases first allocation'})
    assert released.status_code==200,released.text
    with env[1].sessions() as db: assert db.scalar(select(func.sum(Allocation.amount_paisa)))==5000
    results=env[0].get(f'/api/batches/{result["batch"]["id"]}/results',headers=auth).json()['items']
    released_row=next(item for item in results if item['id']==first['match_id'])
    assert released_row['allocated_paisa']==0
    assert not any(e['check']=='reviewed_allocation' for e in released_row['evidence'])


def test_overpayment_is_not_auto_shipped_or_overallocated(env, auth):
    result,lines,claims=funding_case(env,auth,payments=(('150',0,'OVERPAY-001'),))
    assert result['items'][0]['reason_code']=='OVERPAYMENT'
    bad=allocation_body(result,[(0,[(lines['OVERPAY-001'],claims[0],'150')])])
    assert submit(env,auth,result,bad).status_code==422
    good=allocation_body(result,[(0,[(lines['OVERPAY-001'],claims[0],'100')])])
    response=submit(env,auth,result,good)
    assert response.status_code==200,response.text
    statement=env[0].get(f'/api/batches/{result["batch"]["id"]}/statements',headers=auth).json()['items'][0]
    line=env[0].get(f'/api/statements/{statement["id"]}/lines',headers=auth).json()['items'][0]
    assert line['unallocated_paisa']==5000


def test_retry_is_idempotent_and_changed_or_stale_requests_fail(env, auth):
    result,lines,claims=funding_case(env,auth)
    body=allocation_body(result,[(0,[(lines['PAYMENT-001'],claims[0],'60')])])
    response=submit(env,auth,result,body)
    assert response.status_code==200,response.text
    assert submit(env,auth,result,body).json()==response.json()
    with env[1].sessions() as db: assert db.scalar(select(func.count()).select_from(Allocation))==1
    assert submit(env,auth,result,{**body,'reason':'Changed request must use another idempotency key'}).status_code==409
    assert submit(env,auth,result,body,key='different-stale-request').status_code==409


@pytest.mark.parametrize('status,confirmed,complete,refund,expected',[
    ('Pending',True,True,False,422),('Failed',True,True,False,422),('',True,True,False,422),
    ('Successful',False,True,False,422),('Successful',True,False,False,422),
    ('Successful',True,True,True,409),('Reversed',True,True,False,422)])
def test_unsafe_evidence_cannot_support_reviewed_funding(env,auth,status,confirmed,complete,refund,expected):
    result,lines,claims=funding_case(env,auth,status=status,confirmed=confirmed,complete=complete,refund=refund)
    response=submit(env,auth,result,allocation_body(result,[(0,[(lines['PAYMENT-001'],claims[0],'60')])]))
    assert response.status_code==expected,response.text
    with env[1].sessions() as db: assert db.scalar(select(func.count()).select_from(Allocation))==0


def test_plan_blocks_cross_seller_and_cross_batch_evidence(env,auth):
    result,lines,claims=funding_case(env,auth)
    other_result,other_lines,other_claims=funding_case(env,auth)
    body=allocation_body(result,[(0,[(other_lines['PAYMENT-001'],other_claims[0],'60')])])
    assert submit(env,auth,result,body).status_code==422
    other_auth=register(env[0],'second-seller@example.com')
    assert submit(env,other_auth,result,body).status_code==404
    assert env[0].get(f'/api/batches/{result["batch"]["id"]}/results',headers=other_auth).status_code==404


def test_insufficient_credit_in_a_group_rolls_back_every_order(env,auth):
    result,lines,claims=funding_case(env,auth,totals=('100','100'),payments=(('150',0,'GROUP-001'),))
    body=allocation_body(result,[(0,[(lines['GROUP-001'],claims[0],'100')]),(1,[(lines['GROUP-001'],claims[0],'100')])])
    assert submit(env,auth,result,body).status_code==409
    with env[1].sessions() as db:
        assert db.scalar(select(func.count()).select_from(Allocation))==0
        assert all(m.version==1 for m in db.scalars(select(Match)))


def test_concurrent_reviews_cannot_overallocate_retained_credit(env,auth):
    first,lines1,claims1=funding_case(env,auth,totals=('200',),payments=(('100',0,'CONCURRENT-001'),))
    second,lines2,claims2=funding_case(env,auth,totals=('200',),payments=(('100',0,'CONCURRENT-001'),))
    bodies=[allocation_body(first,[(0,[(lines1['CONCURRENT-001'],claims1[0],'100')])]),
            allocation_body(second,[(0,[(lines2['CONCURRENT-001'],claims2[0],'100')])])]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(submit,env,auth,result,body,key=f'concurrent-review-{index}') for index,(result,body) in enumerate(zip([first,second],bodies))]
        responses=[future.result() for future in futures]
    assert sorted(response.status_code for response in responses)==[200,409],[r.text for r in responses]
    with env[1].sessions() as db: assert db.scalar(select(func.sum(Allocation.amount_paisa)))==10000


def test_concurrent_identical_retries_create_one_allocation(env,auth):
    result,lines,claims=funding_case(env,auth)
    body=allocation_body(result,[(0,[(lines['PAYMENT-001'],claims[0],'60')])])
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:submit(env,auth,result,body),range(2)))
    assert [r.status_code for r in responses]==[200,200]
    assert responses[0].json()==responses[1].json()
    with env[1].sessions() as db: assert db.scalar(select(func.count()).select_from(Allocation))==1


def test_reset_releases_all_shares_and_rejects_old_review_replay(env,auth):
    result,lines,claims=funding_case(env,auth,payments=(('60',0,'RESET-001'),('40',0,'RESET-002')))
    body=allocation_body(result,[(0,[(lines['RESET-001'],claims[0],'60'),(lines['RESET-002'],claims[1],'40')])])
    assert submit(env,auth,result,body).status_code==200
    response=env[0].post(f'/api/batches/{result["batch"]["id"]}/reset',headers=auth,
        json={'expected_revision':result['batch']['revision'],'reason':'Synthetic statement updated with new payment evidence'})
    assert response.status_code==200,response.text
    with env[1].sessions() as db: assert db.scalar(select(func.count()).select_from(Allocation))==0
    assert submit(env,auth,result,body).status_code==409


def test_expiry_removes_review_shares_and_retry_records(env,auth):
    from datetime import timedelta
    from app.models import Batch, AllocationReview, now
    from app.jobs import cleanup
    result,lines,claims=funding_case(env,auth)
    body=allocation_body(result,[(0,[(lines['PAYMENT-001'],claims[0],'60')])])
    assert submit(env,auth,result,body).status_code==200
    with env[1].transaction() as db:
        db.get(Batch,result['batch']['id']).expires_at=now()-timedelta(seconds=1)
    cleanup(env[1],env[2])
    with env[1].sessions() as db:
        assert db.scalar(select(func.count()).select_from(Allocation))==0
        assert db.scalar(select(func.count()).select_from(AllocationReview))==0
    assert submit(env,auth,result,body).status_code==404


def test_retained_source_cannot_be_reimported_with_an_inflated_amount(env,auth):
    first,lines1,claims1=funding_case(env,auth,totals=('200',),payments=(('100',0,'SAME-CREDIT'),))
    body1=allocation_body(first,[(0,[(lines1['SAME-CREDIT'],claims1[0],'60')])])
    assert submit(env,auth,first,body1).status_code==200
    second,lines2,claims2=funding_case(env,auth,totals=('200',),payments=(('150',0,'SAME-CREDIT'),))
    body2=allocation_body(second,[(0,[(lines2['SAME-CREDIT'],claims2[0],'20')])])
    response=submit(env,auth,second,body2)
    assert response.status_code==409 and 'conflicts with retained' in response.text


@pytest.mark.parametrize('amount,confirm', [('0',True),('-1',True),('60',False)])
def test_invalid_or_unconfirmed_plan_never_creates_allocations(env,auth,amount,confirm):
    result,lines,claims=funding_case(env,auth)
    body=allocation_body(result,[(0,[(lines['PAYMENT-001'],claims[0],amount)])])
    body['confirmed_relationships']=confirm
    assert submit(env,auth,result,body).status_code==422
    with env[1].sessions() as db: assert db.scalar(select(func.count()).select_from(Allocation))==0


def test_legacy_shipping_cannot_override_same_reference_reversal(env,auth):
    result,lines,claims=funding_case(env,auth,payments=(('100',0,'REVERSED-001'),),refund=True)
    match=result['items'][0]
    assert match['reason_code']=='REVERSAL' and match['final_status']=='review'
    response=env[0].post(f'/api/matches/{match["id"]}/decision',headers=auth,
        json={'expected_version':match['version'],'decision':'ship','statement_line_id':lines['REVERSED-001']['id'],'reason':'Attempt to override unresolved reversal'})
    assert response.status_code==409
    with env[1].sessions() as db: assert db.scalar(select(func.count()).select_from(Allocation))==0


def test_worker_and_human_review_share_the_same_credit_budget_lock(env,auth):
    from app.jobs import run_once
    partial,lines,claims=funding_case(env,auth,totals=('200',),payments=(('100',0,'WORKER-RACE'),))
    automatic,_,_=funding_case(env,auth,totals=('100',),payments=(('100',0,'WORKER-RACE'),),run=False)
    response=env[0].post(f'/api/batches/{automatic["batch"]["id"]}/reconcile',
        headers={**auth,'Idempotency-Key':'worker-allocation-race'})
    assert response.status_code==202
    job_id=response.json()['id']
    body=allocation_body(partial,[(0,[(lines['WORKER-RACE'],claims[0],'100')])])
    with ThreadPoolExecutor(max_workers=2) as pool:
        worker=pool.submit(run_once,env[1],env[2])
        review=pool.submit(submit,env,auth,partial,body)
        assert worker.result() is True
        reviewed=review.result()
    assert reviewed.status_code in [200,409],reviewed.text
    assert env[0].get('/api/jobs/'+job_id,headers=auth).json()['status']=='done'
    result=env[0].get(f'/api/batches/{automatic["batch"]["id"]}/results',headers=auth).json()['items'][0]
    assert result['final_status']==('review' if reviewed.status_code==200 else 'ship')
    with env[1].sessions() as db: assert db.scalar(select(func.sum(Allocation.amount_paisa)))==10000
