import {useEffect,useState} from 'react';
import type {CSSProperties} from 'react';
import {useLocation} from 'react-router-dom';
import {api} from '../lib/api';

type Product={id:string;name:string;description?:string;amount:string;currency:string};
type Checkout={merchant_order_id:string;paypal_order_id:string;approval_url:string;access_token:string;amount:string;currency:string};

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
 const [complaintFile,setComplaintFile]=useState<File|null>(null);
 const [evidenceType,setEvidenceType]=useState('product_photo');
 const [evidenceDescription,setEvidenceDescription]=useState('');
 const [notice,setNotice]=useState('');
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const orderId=params.get('merchant_order_id')||'';
 const access=params.get('access')||'';
 useEffect(()=>{if(!complete&&slug)api<any>('/api/store/'+encodeURIComponent(slug)).then(r=>{setProducts(r.products||[]);setSelected(r.products?.[0]?.id||'');}).catch(e=>setError(e.message));},[slug,complete]);
 useEffect(()=>{if(complete&&orderId&&access){setBusy(true);api<any>('/api/store/order/'+encodeURIComponent(orderId)+'/capture?access='+encodeURIComponent(access),{method:'POST',body:JSON.stringify({})}).then(r=>{if(r.status!=='COMPLETED')throw Error('PayPal has not confirmed a completed capture yet.');setNotice('Payment confirmed by PayPal Sandbox. Your order is now recorded.');return api<any>('/api/store/order/'+encodeURIComponent(orderId)+'?access='+encodeURIComponent(access));}).then(setOrder).catch(e=>setError(e.message)).finally(()=>setBusy(false));}},[complete,orderId,access]);
 async function buy(){setBusy(true);setError('');try{const r=await api<Checkout>('/api/store/'+encodeURIComponent(slug)+'/checkout',{method:'POST',body:JSON.stringify({product_id:selected,customer_name:customerName,customer_email:customerEmail})});sessionStorage.setItem('merchantos_customer_order',JSON.stringify({id:r.merchant_order_id,access:r.access_token}));setCheckout(r);}catch(e:any){setError(e.message);}finally{setBusy(false);}}
 async function complain(){setBusy(true);setError('');try{const r=await api<any>('/api/store/order/'+encodeURIComponent(orderId)+'/complaints?access='+encodeURIComponent(access),{method:'POST',body:JSON.stringify({category,message})});let evidenceNote='';if(complaintFile){const form=new FormData();form.append('file',complaintFile);form.append('evidence_type',evidenceType);form.append('description',evidenceDescription.trim()||'Customer-submitted complaint evidence');await api<any>('/api/store/order/'+encodeURIComponent(orderId)+'/complaints/'+encodeURIComponent(r.case_id)+'/evidence?access='+encodeURIComponent(access),{method:'POST',body:form});evidenceNote=' Evidence uploaded and linked securely.';}setNotice('Complaint submitted. Reference: '+r.complaint_id+'. MerchantOS case: '+r.case_id+'.'+evidenceNote);setMessage('');setComplaintFile(null);setEvidenceDescription('');const refreshed=await api<any>('/api/store/order/'+encodeURIComponent(orderId)+'?access='+encodeURIComponent(access));setOrder(refreshed);}catch(e:any){setError(e.message+' If your complaint was already created, contact the merchant before submitting it again.');}finally{setBusy(false);}}
 const page:CSSProperties={minHeight:'100vh',padding:'28px 16px 56px',background:'radial-gradient(circle at 12% 0%,#f4dfd6 0,transparent 34%),linear-gradient(145deg,#f7f3eb,#e9eee8)',color:'#25221f'};
 const shell:CSSProperties={maxWidth:980,margin:'0 auto'};
 const card:CSSProperties={background:'rgba(255,255,255,.88)',border:'1px solid #e5ddd3',borderRadius:22,padding:24,boxShadow:'0 18px 50px rgba(43,35,29,.07)'};
 const eyebrow:CSSProperties={fontSize:11,letterSpacing:2.5,fontWeight:800,color:'#8b6d5d'};
 const title:CSSProperties={fontFamily:'Georgia,serif',fontSize:'clamp(34px,6vw,56px)',fontWeight:500,lineHeight:1.04,margin:'12px 0'};
 const soft:CSSProperties={color:'#6c716e',lineHeight:1.7};
 const cta:CSSProperties={...button,background:'#762e38',padding:'14px 20px',borderRadius:12};
 return <main style={page}><div style={shell}>
  <header style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:16,marginBottom:26}}><div style={{display:'flex',alignItems:'center',gap:12}}><div style={{width:44,height:44,borderRadius:13,display:'grid',placeItems:'center',background:'#762e38',color:'#fff',fontFamily:'Georgia,serif',fontSize:25}}>M</div><div><b style={{fontFamily:'Georgia,serif',fontSize:22}}>MerchantOS</b><div style={eyebrow}>COMMERCE, WITH CARE</div></div></div><span style={{fontSize:12,color:'#66736a',border:'1px solid #d8e0d8',borderRadius:99,padding:'8px 12px'}}>PAYPAL SANDBOX</span></header>
  {complete?<section style={{...card,maxWidth:760,margin:'0 auto'}}><div style={eyebrow}>YOUR ORDER / CUSTOMER CARE</div><h1 style={title}>Your purchase,<br/>looked after.</h1><p style={soft}>{busy?'Confirming your payment securely with PayPal…':order?'Your order is recorded. Need help? You can tell the store what happened and attach photos or documents.':'Checking your order status.'}</p><div style={{padding:16,background:'#f6f1eb',borderRadius:14,margin:'22px 0'}}><small style={eyebrow}>ORDER REFERENCE</small><h3 style={{margin:'6px 0'}}>{orderId}</h3>{order&&<p style={{margin:0}}>{order.product} · {order.amount} {order.currency} · <b>{order.payment_status}</b></p>}</div>
  {order&&<><div style={{borderTop:'1px solid #ece6df',paddingTop:20}}><div style={eyebrow}>CUSTOMER SUPPORT</div><h2 style={{fontFamily:'Georgia,serif',fontSize:30,fontWeight:500,margin:'8px 0'}}>Something not right?</h2><p style={soft}>Tell us what went wrong. Your message and attached evidence will be linked to this order for the merchant to review.</p><label style={field}>What happened?<select style={input} value={category} onChange={e=>setCategory(e.target.value)}><option value="DAMAGED">Damaged item</option><option value="WRONG_ITEM">Wrong item received</option><option value="NOT_RECEIVED">Order not received</option><option value="QUALITY">Product quality</option><option value="OTHER">Something else</option></select></label><label style={field}>Describe the issue<textarea style={{...input,minHeight:120,resize:'vertical'}} value={message} onChange={e=>setMessage(e.target.value)} placeholder="Share the details that will help the store understand…"/></label><div style={{padding:18,border:'1px dashed #b9c6bc',borderRadius:16,background:'#f8faf7',margin:'16px 0'}}><b style={{fontSize:16}}>Attach evidence (optional)</b><p style={soft}>Add a product photo, delivery receipt, screenshot or PDF. Files are securely linked to this complaint.</p><label style={field}>Evidence type<select style={input} value={evidenceType} onChange={e=>setEvidenceType(e.target.value)}><option value="product_photo">Product photo</option><option value="courier_receipt">Courier receipt</option><option value="customer_screenshot">Screenshot</option><option value="order_document">Order document</option><option value="other">Other</option></select></label><label style={field}>Evidence description<input style={input} value={evidenceDescription} onChange={e=>setEvidenceDescription(e.target.value)} placeholder="What does this file show?"/></label><label style={field}>Choose file<input style={input} type="file" accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf" onChange={e=>setComplaintFile(e.target.files?.[0]||null)}/></label><small style={soft}>JPEG, PNG or PDF · maximum 5 MB.</small>{complaintFile&&<p style={{fontSize:13,marginBottom:0}}>Selected: <b>{complaintFile.name}</b></p>}</div><button style={cta} disabled={busy||message.trim().length<10||(!!complaintFile&&evidenceDescription.trim().length>0&&evidenceDescription.trim().length<5)} onClick={complain}>{busy?'Submitting securely…':'Submit complaint'+(complaintFile?' & evidence':'')}</button></div><h3 style={{fontFamily:'Georgia,serif',fontWeight:500,marginTop:28}}>Previous complaints</h3>{(order.complaints||[]).map((x:any)=><article key={x.id} style={{padding:'12px 0',borderTop:'1px solid #eee7df'}}><b>{x.category.replace(/_/g,' ')}</b><p style={{...soft,margin:'5px 0'}}>{x.text}</p><small style={soft}>{x.id}</small></article>)}</>}</section>:<><section style={{...card,display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(260px,1fr))',gap:24,alignItems:'center'}}><div><div style={eyebrow}>A THOUGHTFUL WAY TO SHOP</div><h1 style={title}>Good things.<br/><i style={{color:'#8d4b4e'}}>Better care.</i></h1><p style={soft}>Explore the collection, choose what you love, and check out securely with PayPal Sandbox. This is a demonstration store; no real money is used.</p><div style={{display:'flex',gap:10,flexWrap:'wrap',marginTop:18}}><span style={{background:'#edf2eb',padding:'8px 12px',borderRadius:99,fontSize:12}}>Secure checkout</span><span style={{background:'#f5eee9',padding:'8px 12px',borderRadius:99,fontSize:12}}>Customer support</span></div></div><div style={{minHeight:220,borderRadius:18,background:'linear-gradient(145deg,#e9d7c9,#c7d3c5)',display:'grid',placeItems:'center',padding:24,textAlign:'center'}}><div><div style={{fontFamily:'Georgia,serif',fontSize:76,color:'#762e38'}}>M</div><b style={{fontFamily:'Georgia,serif',fontSize:23}}>Made to matter.</b><p style={{...soft,marginBottom:0}}>A clear, calm shopping experience.</p></div></div></section><section style={{marginTop:26}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'end',gap:12,marginBottom:14}}><div><div style={eyebrow}>THE COLLECTION</div><h2 style={{fontFamily:'Georgia,serif',fontWeight:500,fontSize:32,margin:'5px 0'}}>Shop the store</h2></div><small style={soft}>{products.length} item{products.length===1?'':'s'}</small></div><div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(230px,1fr))',gap:16}}>{products.map(p=><label key={p.id} style={{...card,display:'block',cursor:'pointer',border:selected===p.id?'2px solid #762e38':'1px solid #e5ddd3',padding:18}}><input type="radio" checked={selected===p.id} onChange={()=>setSelected(p.id)} style={{accentColor:'#762e38'}}/><div style={{height:120,borderRadius:14,background:'linear-gradient(145deg,#f1e5dc,#e2e9df)',display:'grid',placeItems:'center',fontFamily:'Georgia,serif',fontSize:44,color:'#8a4a4d',margin:'12px 0'}}>✳</div><h3 style={{fontFamily:'Georgia,serif',fontWeight:500,fontSize:23,margin:'8px 0'}}>{p.name}</h3><p style={soft}>{p.description}</p><strong style={{fontSize:18}}>{p.amount} {p.currency}</strong></label>)}</div><section style={{...card,marginTop:18}}><div style={eyebrow}>CHECKOUT</div><h2 style={{fontFamily:'Georgia,serif',fontWeight:500}}>Ready when you are.</h2><div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:12}}><label style={field}>Your name<input style={input} value={customerName} onChange={e=>setCustomerName(e.target.value)}/></label><label style={field}>Email<input style={input} type="email" value={customerEmail} onChange={e=>setCustomerEmail(e.target.value)}/></label></div><button style={cta} disabled={busy||!selected} onClick={buy}>{busy?'Preparing secure checkout…':'Continue to PayPal checkout ↗'}</button></section></section></>}
  {checkout&&<section style={{...card,marginTop:18}}><b>PayPal checkout is ready</b><p style={soft}>Your order is created. Continue on PayPal's secure Sandbox checkout page.</p><a href={checkout.approval_url} style={{...cta,display:'inline-block',textDecoration:'none'}}>Continue to PayPal Checkout ↗</a><p style={{fontSize:12,overflowWrap:'anywhere'}}>PayPal order: {checkout.paypal_order_id}</p></section>}
  {notice&&<div style={{...note,marginTop:16}}>{notice}</div>}{error&&<div style={{...errorStyle,marginTop:16}}>{error}</div>}
  <footer style={{textAlign:'center',padding:28,...soft}}>MERCHANTOS · CUSTOMER EXPERIENCE & TRUST</footer>
 </div></main>;
}
