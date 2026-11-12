import {useEffect,useState} from 'react';
import type {CSSProperties} from 'react';
import {useLocation} from 'react-router-dom';
import {api} from '../lib/api';

type Product={id:string;name:string;description?:string;amount:string;currency:string};
type Checkout={merchant_order_id:string;approval_url:string;access_token:string;amount:string;currency:string};

const box:CSSProperties={maxWidth:760,margin:'32px auto',padding:24,border:'1px solid #dbe2ea',borderRadius:18,background:'#fff',color:'#172033'};
const field:React.CSSProperties={display:'grid',gap:6,margin:'12px 0',fontSize:13,fontWeight:650};
const input:React.CSSProperties={padding:12,border:'1px solid #cbd5e1',borderRadius:9,width:'100%',boxSizing:'border-box'};
const button:React.CSSProperties={padding:'12px 16px',border:0,borderRadius:9,background:'#172554',color:'#fff',fontWeight:750,cursor:'pointer'};
const note:React.CSSProperties={padding:12,borderRadius:9,background:'#eff6ff',color:'#1e40af',marginTop:12};
const errorStyle:React.CSSProperties={padding:12,borderRadius:9,background:'#fef2f2',color:'#991b1b',marginTop:12};

export function StorefrontAdmin(){
 const [slug,setSlug]=useState('merchantos-demo');
 const [name,setName]=useState('Demo Product');
 const [description,setDescription]=useState('A sample product for the live PayPal Sandbox journey.');
 const [amount,setAmount]=useState('25.00');
 const [currency,setCurrency]=useState('USD');
 const [clientId,setClientId]=useState('');
 const [clientSecret,setClientSecret]=useState('');
 const [paypalConnected,setPaypalConnected]=useState(false);
 const [storeUrl,setStoreUrl]=useState('');
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 useEffect(()=>{api<any>('/api/v1/paypal-connection/status').then(r=>setPaypalConnected(!!r.connected)).catch(()=>setPaypalConnected(false));},[]);
 async function connectPaypal(){setBusy(true);setError('');try{await api('/api/v1/paypal-connection/connect',{method:'POST',body:JSON.stringify({client_id:clientId,client_secret:clientSecret,environment:'sandbox'})});setPaypalConnected(true);setClientSecret('');}catch(e:any){setError(e.message||'PayPal Sandbox connection failed.');}finally{setBusy(false);}}
 async function save(){
  setBusy(true);setError('');
  try{const r=await api<any>('/api/v1/storefront/setup',{method:'POST',body:JSON.stringify({slug,products:[{id:'demo-product',name,description,amount,currency}]})});setStoreUrl(window.location.origin+r.store_path);}
  catch(e:any){setError(e.message||'Could not configure storefront.');}
  finally{setBusy(false);}
 }
 return <main style={box}><div style={{fontSize:11,letterSpacing:2,fontWeight:800,color:'#64748b'}}>CUSTOMER EXPERIENCE / STOREFRONT</div><h1>Launch your Sandbox store</h1><p>Configure a product catalogue. Customers can purchase through PayPal Sandbox and submit complaints against captured orders.</p>
  <h2>1. Connect PayPal Sandbox</h2><p>Use your PayPal Developer app Sandbox Client ID and Secret. The backend encrypts the secret and never returns it.</p><label style={field}>Sandbox Client ID<input style={input} value={clientId} onChange={e=>setClientId(e.target.value)} autoComplete="off"/></label><label style={field}>Sandbox Client Secret<input style={input} type="password" value={clientSecret} onChange={e=>setClientSecret(e.target.value)} autoComplete="new-password"/></label><button style={button} disabled={busy||clientId.length<10||clientSecret.length<10} onClick={connectPaypal}>{busy?'Connecting…':'Connect PayPal Sandbox'}</button><div style={note}>{paypalConnected?'PayPal Sandbox connection is active.':'PayPal Sandbox is not connected yet.'}</div><h2>2. Configure product catalogue</h2>
  <label style={field}>Store URL slug<input style={input} value={slug} onChange={e=>setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g,''))}/></label>
  <label style={field}>Product name<input style={input} value={name} onChange={e=>setName(e.target.value)}/></label>
  <label style={field}>Description<input style={input} value={description} onChange={e=>setDescription(e.target.value)}/></label>
  <div style={{display:'grid',gridTemplateColumns:'2fr 1fr',gap:12}}><label style={field}>Price<input style={input} type="number" min="0.01" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)}/></label><label style={field}>Currency<select style={input} value={currency} onChange={e=>setCurrency(e.target.value)}><option>USD</option><option>EUR</option><option>GBP</option></select></label></div>
  <button style={button} disabled={busy} onClick={save}>{busy?'Saving…':'Save & publish storefront'}</button>
  {error&&<div style={errorStyle}>{error}</div>}
  {storeUrl&&<div style={note}><b>Storefront ready</b><p><a href={storeUrl}>{storeUrl}</a></p><p>Open this link in a private/incognito tab to act as the customer. PayPal Sandbox credentials must already be connected.</p></div>}
 </main>;
}

export function StorefrontPage(){
 const location=useLocation();
 const params=new URLSearchParams(location.search);
 const complete=location.pathname==='/store/complete';
 const slug=location.pathname.split('/')[2]||'';
 const [products,setProducts]=useState<Product[]>([]);
 const [selected,setSelected]=useState('');
 const [customerName,setCustomerName]=useState('Sandbox Buyer');
 const [customerEmail,setCustomerEmail]=useState('buyer@example.test');
 const [checkout,setCheckout]=useState<Checkout|null>(null);
 const [order,setOrder]=useState<any>(null);
 const [category,setCategory]=useState('DAMAGED');
 const [message,setMessage]=useState('');
 const [notice,setNotice]=useState('');
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const orderId=params.get('merchant_order_id')||'';
 const access=params.get('access')||'';
 useEffect(()=>{if(!complete&&slug)api<any>('/api/store/'+encodeURIComponent(slug)).then(r=>{setProducts(r.products||[]);setSelected(r.products?.[0]?.id||'');}).catch(e=>setError(e.message));},[slug,complete]);
 useEffect(()=>{if(complete&&orderId&&access){setBusy(true);api<any>('/api/store/order/'+encodeURIComponent(orderId)+'/capture?access='+encodeURIComponent(access),{method:'POST',body:JSON.stringify({})}).then(r=>{if(r.status!=='COMPLETED')throw Error('PayPal has not confirmed a completed capture yet.');setNotice('Payment confirmed by PayPal Sandbox. Your order is now recorded.');return api<any>('/api/store/order/'+encodeURIComponent(orderId)+'?access='+encodeURIComponent(access));}).then(setOrder).catch(e=>setError(e.message)).finally(()=>setBusy(false));}},[complete,orderId,access]);
 async function buy(){setBusy(true);setError('');try{const r=await api<Checkout>('/api/store/'+encodeURIComponent(slug)+'/checkout',{method:'POST',body:JSON.stringify({product_id:selected,customer_name:customerName,customer_email:customerEmail})});sessionStorage.setItem('merchantos_customer_order',JSON.stringify({id:r.merchant_order_id,access:r.access_token}));setCheckout(r);}catch(e:any){setError(e.message);}finally{setBusy(false);}}
 async function complain(){setBusy(true);setError('');try{const r=await api<any>('/api/store/order/'+encodeURIComponent(orderId)+'/complaints?access='+encodeURIComponent(access),{method:'POST',body:JSON.stringify({category,message})});setNotice('Complaint submitted. Reference: '+r.complaint_id+'. MerchantOS case: '+r.case_id);setMessage('');const refreshed=await api<any>('/api/store/order/'+encodeURIComponent(orderId)+'?access='+encodeURIComponent(access));setOrder(refreshed);}catch(e:any){setError(e.message);}finally{setBusy(false);}}
 return <main style={box}><div style={{fontSize:11,letterSpacing:2,fontWeight:800,color:'#64748b'}}>MERCHANTOS / CUSTOMER PORTAL / PAYPAL SANDBOX</div>
 {complete?<><h1>Order confirmation</h1><p>{busy?'Confirming your payment with PayPal…':order?'Your order is recorded.':'Checking your order status.'}</p><p><b>Order:</b> {orderId}</p>{order&&<><p>{order.product} · {order.amount} {order.currency} · <b>{order.payment_status}</b></p><h2>Report a problem</h2><p>Tell the merchant what went wrong. Your complaint will appear in their MerchantOS investigation queue.</p><label style={field}>Issue category<select style={input} value={category} onChange={e=>setCategory(e.target.value)}><option value="DAMAGED">Damaged item</option><option value="WRONG_ITEM">Wrong item</option><option value="NOT_RECEIVED">Not received</option><option value="QUALITY">Product quality</option><option value="OTHER">Other</option></select></label><label style={field}>What happened?<textarea style={{...input,minHeight:110}} value={message} onChange={e=>setMessage(e.target.value)} placeholder="Describe the issue (at least 10 characters)…"/></label><button style={button} disabled={busy||message.trim().length<10} onClick={complain}>Submit complaint</button><h3>Previous complaints</h3>{(order.complaints||[]).map((x:any)=><p key={x.id}>{x.category}: {x.text}</p>)}</>}</>:<><h1>MerchantOS Demo Store</h1><p>Purchase with a PayPal Sandbox buyer account. No real money is used.</p>{products.map(p=><label key={p.id} style={{display:'block',padding:16,border:'1px solid #dbe2ea',borderRadius:12,margin:'12px 0'}}><input type="radio" checked={selected===p.id} onChange={()=>setSelected(p.id)}/> <b>{p.name}</b><p>{p.description}</p><strong>{p.amount} {p.currency}</strong></label>)}<label style={field}>Your name<input style={input} value={customerName} onChange={e=>setCustomerName(e.target.value)}/></label><label style={field}>Email<input style={input} type="email" value={customerEmail} onChange={e=>setCustomerEmail(e.target.value)}/></label><button style={button} disabled={busy||!selected} onClick={buy}>{busy?'Preparing PayPal checkout…':'Create PayPal checkout link'}</button>
 {checkout&&<div style={note}><b>PayPal checkout is ready</b><p>Your order has been created. Continue on PayPal's secure Sandbox checkout page to approve the payment.</p><a href={checkout.approval_url} style={{...button,display:'inline-block',textDecoration:'none'}} onClick={()=>{}}>Continue to PayPal Checkout ↗</a><p style={{fontSize:12,overflowWrap:'anywhere'}}>PayPal order: {checkout.paypal_order_id}</p></div>}</>}
 {notice&&<div style={note}>{notice}</div>}{error&&<div style={errorStyle}>{error}</div>}
 </main>;
}
