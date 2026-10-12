# Bilal, simple tareeqa

Yeh Milaan ka actual backend hai. Isme user accounts, database, screenshot upload, AI reader ka connection, payment matching, review aur CSV download ka code hai.

## Pehle run karo

1. ZIP extract karo.
2. Python **3.12** install ho. Tumhara 3.13 alag reh sakta hai; `py -3.12` specifically 3.12 use karega.
3. `milaan-backend` folder mein `start.bat` chalao.
4. Pehli dafa packages download honge aur database banega. Terminal khula rehne do.
5. Browser mein `http://127.0.0.1:8000/docs` kholo.

Backend band karna ho to terminal mein Ctrl+C. Dobara `start.bat` chalao to saved data wapas milega.

## Asaan demo screen

Isi folder mein doosra terminal kholo:

```bat
py -3.12 -m http.server 8080 --directory integration
```

`http://localhost:8080` kholo. Apna account banao, phir **Create + reconcile sample** dabao. 12 sample orders database mein save honge: 5 Ship, 2 Hold, 5 Review. Is sample ke liye Gemini key nahi chahiye.

## Real screenshots ka flow

1. Batch banao: matlab aaj ke orders ka ek group.
2. Orders ki CSV upload karo.
3. Apni receiving wallet/bank statement ki CSV upload karo. Template `samples/statement.csv` mein hai.
4. Har screenshot ko uske order ke saath upload karo.
5. Screenshot ke fields khud check karke save karo, ya Gemini key configure karke AI se read karwao.
6. Reconcile chalao. Backend statement se match karega.
7. Review wale cases insaan check karega. Final CSV download kar lo.

**Ship:** uploaded statement mein suitable matching credit mila. **Hold:** supplied statement mein match nahi mila. **Review:** evidence unclear ya conflicting hai. Yeh bank se direct confirmation nahi leta.

## AI key kahan lagegi?

Backend ki `.env` file mein:

```dotenv
EXTRACTION_PROVIDER=gemini
GEMINI_API_KEY=apni-key-yahan
GEMINI_MODEL=apne-account-ka-supported-model-id
```

Key website ke JavaScript mein kabhi mat daalna. Backend restart karo. Extraction request mein user ki ijazat ke baad `consent_to_cloud: true` bhejna hai; tab screenshot Google ko jayega. Key ke baghair manual entry aur matching dono chalenge.

## Website se kaise connect hoga?

Frontend wale teammate ko `integration/milaan-api.js` aur `docs/FRONTEND.md` do. Usme functions ready hain: login, upload, extract, reconcile, review aur export. Existing website ke local buttons ko in calls se connect karna hai. Sirf ZIP download karne se hosted website automatically connect nahi hoti.

## Yaad rakhna

- Default mein batch **7 din baad delete** ho jata hai. `.env` ka `BATCH_RETENTION_HOURS` apni need ke mutabiq set karo; yeh new batches par lagega.
- `data/` folder mein local database aur receipt files banti hain. Isko delete karoge to local data chala jayega.
- Public website ke liye backend bhi HTTPS par host karna hoga. Laptop ka localhost doosre log use nahi kar sakte.
- `docs/API.md` mein endpoints aur exact data formats hain. `/docs` se APIs test bhi kar sakte ho.

Teammates ko ek line mein: **Frontend screen dikhata hai; backend data save karta hai, screenshot read karwata hai, statement se matching karta hai aur final result wapas deta hai.**
