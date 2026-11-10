const API = import.meta.env.VITE_API_BASE ?? '';
export function token(){return localStorage.getItem('merchantos_token') ?? '';}
export async function api<T=any>(path:string, init:RequestInit={}):Promise<T>{
 const headers=new Headers(init.headers); headers.set('Accept','application/json');
 if(init.body && !(init.body instanceof FormData)) headers.set('Content-Type','application/json');
 if(token()) headers.set('Authorization',`Bearer ${token()}`);
 const res=await fetch(`${API}${path}`,{...init,headers});
 if(!res.ok){const body=await res.json().catch(()=>({detail:res.statusText})); throw new Error(body.detail||`Request failed (${res.status})`);}
 return res.status===204?undefined as T:res.json();
}
export const money=(v:number,c='INR')=>new Intl.NumberFormat('en-IN',{style:'currency',currency:c,maximumFractionDigits:2}).format(v||0);
