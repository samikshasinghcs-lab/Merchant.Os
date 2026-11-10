import json,random,csv
from pathlib import Path
random.seed(19);base=Path(__file__).parent
names=["Aarav","Mira","Kabir","Anaya","Ishaan","Riya","Dev","Tara","Arjun","Nisha","Vihaan","Sana","Reyansh","Ira","Aditya"]
products=["Hydrating Serum","Vitamin C Serum","Daily Moisturizer"];batches=["BATCH-A","BATCH-B","BATCH-C"]
orders=[]
for i in range(15):
 orders.append({"id":f"ORD-{i+1:03}","customer_id":f"CUST-{i+1:03}","customer_name":names[i],"product":products[i%3],"batch":"BATCH-B" if i in [1,4,7,10,13] else batches[i%3],"amount":[499,599,399][i%3],"currency":"INR","paypal_order_id":f"ILLUSTRATIVE-ORDER-{i+1:03}","capture_id":f"ILLUSTRATIVE-CAPTURE-{i+1:03}","payment_status":"COMPLETED","created_at":f"2026-11-{i%9+1:02}T10:00:00Z"})
texts=["The bottle arrived broken and packaging was crushed.","My serum is leaking from the pump, half empty.","Delivery was late and arrived three days after estimate.","I received the wrong item, not what I ordered.","Product quality is disappointing and the pump does not work.","Packaging was damaged when it arrived.","The bottle leaked inside the parcel.","Shipping was delayed but product is fine."]
reviews=[]
for i in range(40):
 oi=i%15;txt=texts[(i*7+i//5)%len(texts)]
 if oi in [1,4,7,10,13] and i%3:txt="The bottle arrived damaged and serum was leaking inside crushed packaging."
 reviews.append({"id":f"REV-{i+1:03}","customer_id":orders[oi]["customer_id"],"customer_name":orders[oi]["customer_name"],"order_id":orders[oi]["id"],"product":orders[oi]["product"],"rating":random.choice([1,2,2,3,4,5]),"text":txt,"created_at":f"2026-11-{i%9+1:02}T12:{i%60:02}Z","cluster_id":None,"category":None,"severity":None})
disputes=[
{"id":"DSP-001","order_id":"ORD-002","reason":"Product not received","status":"OPEN","customer_message":"I have not received my parcel.","evidence":["order_confirmation","payment_record","shipping_reference_pending"]},
{"id":"DSP-002","order_id":"ORD-005","reason":"Product not as described","status":"OPEN","customer_message":"The item arrived damaged.","evidence":["order_confirmation","customer_review","customer_photograph_pending"]},
{"id":"DSP-003","order_id":"ORD-008","reason":"Credit not processed","status":"OPEN","customer_message":"I was told I would receive a refund.","evidence":["order_confirmation","support_message"]},
{"id":"DSP-004","order_id":"ORD-011","reason":"Product not received","status":"UNDER_REVIEW","customer_message":"Tracking has not updated.","evidence":["order_confirmation","tracking_snapshot"]},
{"id":"DSP-005","order_id":"ORD-014","reason":"Duplicate transaction","status":"OPEN","customer_message":"I believe I was charged twice.","evidence":["payment_record","order_confirmation"]}]
(base/"seed_data.json").write_text(json.dumps({"orders":orders,"reviews":reviews,"disputes":disputes},indent=2))
with (base/"reviews.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=reviews[0]);w.writeheader();w.writerows(reviews)
print("Generated 15 illustrative orders, 40 reviews and 5 illustrative disputes.")
