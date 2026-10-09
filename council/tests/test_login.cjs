const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../oppencouncil/assets/freeze_login.js'),'utf8');
const settle=()=>new Promise(setImmediate);
async function login({setup=true,authenticated=false,fail=null}={}) {
  const elements={},calls=[],destinations=[];
  const el=id=>elements[id] ||= {value:'',type:'password',hidden:true,dataset:{},listeners:{},
    addEventListener(name,callback){this.listeners[name]=callback;},setAttribute(){},focus(){}};
  vm.runInNewContext(source,{
    document:{getElementById:el},AbortController,setTimeout,clearTimeout,TypeError,
    location:{pathname:'/projects/test/freeze',search:'?question=F-000007',hash:'#key=obsolete',replace:target=>destinations.push(target)},
    history:{replaceState:(_,__,target)=>destinations.push('clean:'+target)},
    fetch:async(url,options)=>{
      if (url==='/api/auth') return {ok:true,json:async()=>({setup_required:setup,authenticated})};
      calls.push({url,body:JSON.parse(options.body)});
      if(fail) return {ok:false,status:fail.status,json:async()=>({error:fail.message})};
      return {ok:true,json:async()=>({ok:true})};
    },
    localStorage:{setItem(){throw new Error('Password must not be stored');}},
    sessionStorage:{setItem(){throw new Error('Password must not be stored');}},
  });
  await settle();
  return {el,calls,destinations,submit:()=>el('login-form').listeners.submit({preventDefault(){}})};
}
test('first visit requests matching passwords and preserves the deep link after setup',async()=>{
  const app=await login();
  assert.equal(app.el('confirmation-row').hidden,false);
  assert.equal(app.el('heading').textContent,'设置站点密码');
  app.el('password').value='synthetic-password';app.el('confirmation').value='different';
  await app.submit();assert.equal(app.calls.length,0);assert.match(app.el('message').textContent,/不一致/);
  app.el('confirmation').value='synthetic-password';await app.submit();
  assert.equal(app.calls[0].url,'/api/setup');assert.equal(app.el('password').value,'');
  assert.equal(app.destinations.at(-1),'/projects/test/freeze?question=F-000007');
});
test('later login uses only password and keeps failure visible without navigating',async()=>{
  const app=await login({setup:false,fail:{status:403,message:'密码不正确，请重试。'}});
  assert.equal(app.el('confirmation-row').hidden,true);
  app.el('password').value='synthetic-password';await app.submit();
  assert.equal(app.calls[0].url,'/api/login');assert.deepEqual(app.calls[0].body,{password:'synthetic-password'});
  assert.match(app.el('message').textContent,/不正确/);assert.equal(app.el('submit').disabled,false);
  assert.equal(app.destinations.length,1);
});
test('password visibility is controlled by the page and successful login returns to the question',async()=>{
  const app=await login({setup:false});app.el('reveal').listeners.click();
  assert.equal(app.el('password').type,'text');app.el('reveal').listeners.click();
  assert.equal(app.el('password').type,'password');
  app.el('password').value='synthetic-password';await app.submit();
  assert.equal(app.destinations.at(-1),'/projects/test/freeze?question=F-000007');
});
test('an authenticated browser returns to its original route without a password prompt',async()=>{
  const app=await login({authenticated:true});
  assert.equal(app.destinations.at(-1),'/projects/test/freeze?question=F-000007');
  assert.equal(app.el('login-form').hidden,true);
});
