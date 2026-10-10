# 5–7 minute live demo

## Demo se pehle

SETUP.bat ek martaba run karo, phir START_DEMO.bat. Dono terminals khulay rehne do.

Do browser tabs kholo:

- **Milaan:** http://127.0.0.1:8000 — receipt checker.
- **Demo store:** http://127.0.0.1:8090 — alag shop.

Dono mein setup wala operator login use karo. Milaan par **Use your own files** se workspace/sign-in kholo, phir **Saved batches** use karo. Milaan ka “See Milaan in action” built-in fictional example hai. Connected store ka demo dikhane ke liye **Saved batches** use karo.

## Part 1 — live API connection

1. Store par customer name aur product choose karo.
2. Scenario **Correct payment** select karo aur **Place demo order** dabao.
3. Order card par **Quick fixture test → Milaan** dabao.
4. Result kuch seconds mein **SHIP** hoga. Yeh result Milaan ke real backend se aa raha hai.
5. Milaan tab → **Saved batches** dubara kholo / refresh karo. `DEMO STORE · DEMO-...` wala matching order reference select karo.
6. Result khol kar receipt, bank credit, amount aur reference dikhao.

Bolne ki simple line:

> Yeh shop alag hai. Is ne order, receipt aur bank record API se Milaan ko bheja. Milaan apne database aur matching logic se decision deta hai. Is demo mein payment aur bank record simulated hain.

**Quick fixture test image OCR ko bypass karta hai:** known test receipt fields API se confirm hoti hain. Is mode ko AI receipt-reading proof mat kehna.

## Part 2 — problem cases

Har case ke liye naya order banao, phir Quick fixture test dabao:

| Store scenario | Expected Milaan result | Demo mein kya samjhana hai |
| --- | --- | --- |
| Correct payment | Ship / EXACT_MATCH | Amount aur full reference statement se match hue |
| Receipt but no matching bank credit | Hold / NOT_FOUND | Screenshot hai, matching bank credit nahi |
| Wrong receipt amount | Review / AMOUNT_CONFLICT | Claimed amount aur order total different hain |
| Same receipt on two orders | Dono Review / REUSED_PROOF | Ek proof do orders ke liye use hua |
| Pakistani name variation | Review / POSSIBLE_MATCH | AiCON “M Ahmed” aur “Muhammad Ahmed” ko similar names samajhta hai |

Name case mein store result aur Milaan evidence drawer mein AiCON score dikhega. Yeh **name similarity** hai, payment hone ka confidence percentage nahi. Name similarity akelay auto-Ship nahi karti.

## Part 3 — actual receipt reading

1. Naya **Correct payment** order banao.
2. **Test receipt reading → Milaan** dabao.
3. Milaan → Saved batches mein yeh order kholo → Import center.
4. Gemini configured ho to AI read control use karo; image bhejne ka confirmation accept karo. Fields inspect karo. AI ko demo watermark ki wajah se proof uncertain lag sakta hai; yeh valid behavior hai.
5. Gemini unavailable ho to receipt dekh kar amount/reference/date fields manually enter karo, checked confirm karo aur Save karo.
6. **Reconcile batch** dabao. Store tab result ko har 3 seconds mein refresh karta hai.

Quick test matching pipeline test karta hai. Receipt mode upload → AI/manual read → matching ka full operator workflow test karta hai.

## Present karte waqt

- “Ship” ek recommendation hai; parcel dispatch nahi hota aur money transfer nahi hota.
- Missing credit ko current engine **Hold** kehta hai; isko implemented delayed-settlement/Pending engine mat claim karna.
- Bank feed yahan simulated CSV hai. Live banking / Shopify integration abhi nahi hai.
- Friends ke baki AI modules abhi pending hain. AiCON name matcher preserved hai; complete ML pipeline active hone ka claim nahi karna.

## Agar issue aaye

- **Port already in use:** purani app ke terminals band karo, phir START_DEMO.bat.
- **Login fail:** setup wali exact email/password; store ko Milaan start hone ke baad connect karo. Account already created ho to sirf .env password change karne se uska DB password nahi badalta.
- **Result nahi aya:** Milaan terminal check karo; RUN_WORKER_IN_API=true hona chahiye. Receipt mode mein reading/save/reconcile manually zaroori hai.
- **Batch store par sent, Milaan par missing:** Saved batches dobara open karo aur same seller account use karo.
- **Session expired/server restarted:** dono apps mein login/reconnect karo. Store password save nahi karta.
- **Upload midway fail:** saved batch Milaan mein inspect karo. Automatic duplicate retry nahi hoti; demo ke liye naya order banao.
- **Wrong backend remembered:** sign-in dialog ka backend URL manually http://127.0.0.1:8000 set karo.

## 9 ghanton ka suggested plan

- Pehle 1 ghante mein local setup + all five demo cases.
- Agle 4 ghante friends ke modules aane par isolated integration + same inputs par verification.
- Agle 2 ghante full rehearsal, screenshots/video backup, final feature list freeze.
- Aakhri 2 ghante domain/deployment + deployed smoke test. Local working demo ko backup rakho.

Domain khareedna hosting nahi hota. Deployment par Milaan aur store alag services/origins rahenge; store ka MILAAN_URL deployed backend se connect hoga. TLS, secure cookies, persistent storage, email configuration aur production access controls deployment stage mein configure/test karne hain. Local demo store ko seedha public production shop mat samajhna.
