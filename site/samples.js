/* Example decisions, one per template. Vendor and product names are invented. */
(function (root) {
const S = {};

S['tech-choice'] = {
  title:'Deliver live order updates with Server-Sent Events', status:'accepted', date:'2026-10-12',
  context:['Customers refresh the order page every few seconds while a courier is on the way. That polling is 38% of API traffic at dinner peak, and status changes still reach the screen up to 30 seconds late.'],
  question:'How should the web and mobile apps receive order status changes as they happen?',
  options:[{id:'sse', name:'Server-Sent Events', desc:'Browser `EventSource` over a long-lived HTTP response.'},{id:'ws', name:'WebSockets'},{id:'lp', name:'Long polling'},{id:'push', name:'Managed push service'}],
  chosen:'sse', because:'it gives sub-second one-way delivery over plain HTTP, passes the proxies that break WebSockets for 6% of sessions, and runs on the gateway we already operate.',
  criteria:[{id:'lat', name:'Latency: status reaches the screen within 2 s', weight:2},{id:'prx', name:'Works behind corporate proxies', weight:3},{id:'ops', name:'Low operational cost for a 4-person team', weight:1},{id:'bat', name:'Mobile battery drain does not get worse', weight:1},{id:'dir', name:'One-way traffic is enough', weight:1}],
  ratings:{lat:{sse:1, ws:2, lp:0, push:2}, prx:{sse:2, ws:-2, lp:2, push:2}, ops:{sse:2, ws:-1, lp:1, push:-1}, bat:{sse:1, ws:1, lp:-2, push:1}, dir:{sse:1, ws:0, lp:0, push:1}},
  metrics:[{name:'p95 delivery latency', unit:'ms', better:'low', values:{sse:420, ws:180, lp:1100, push:300}}],
  consequences:{good:['Order-page polling goes away, about 38% of peak API load','It reuses our HTTP auth, logging and load balancer'], bad:['Each open connection holds a gateway slot, so limits must rise before Black Friday','Two-way courier chat would need a second channel'], neutral:['iOS background delivery still relies on APNs push']},
  confirmation:[{metric:'p95 status-to-screen', target:'< 2 s', by:'two weeks after rollout', how:'Latency dashboard'},{metric:'Polling endpoints left', target:'0', by:'end of Q4', how:'Architecture review'}],
  people:{decided:['Priya Raman','Marco Silva'], consulted:['Mobile team','SRE on-call'], informed:['Customer Support','Product']},
  prosCons:{sse:[{kind:'good', text:'Runs over plain HTTP and passes corporate proxies'},{kind:'good', text:'Reconnect and `Last-Event-ID` resume are built in'},{kind:'neutral', text:'One legacy Android WebView needs a polyfill'},{kind:'bad', text:'One-way only'}],
    ws:[{kind:'good', text:'Two-way and widely supported'},{kind:'good', text:'Lowest latency'},{kind:'bad', text:'6% of sessions sit behind proxies that drop the upgrade'},{kind:'bad', text:'Needs sticky sessions and a separate scaling path'}],
    lp:[{kind:'good', text:'Works everywhere'},{kind:'bad', text:'A new request per message drains mobile battery'},{kind:'bad', text:'Server load stays close to today'}],
    push:[{kind:'good', text:'No infrastructure to run'},{kind:'bad', text:'About $2,400 a month at current volume'},{kind:'bad', text:'Order data leaves our network'}]},
  risks:[{text:'Gateway connection limits hit during peak', likelihood:3, impact:4, mitigation:'Raise limits and load-test at 3× peak before Black Friday'},{text:'Proxy buffering delays events', likelihood:2, impact:3, mitigation:'Send a heartbeat comment every 15 s'}]
};

S['vendor-select'] = {
  title:'Choose an error-monitoring vendor', status:'proposed', date:'2026-10-20',
  context:['Our self-built error alerts miss crashes in the mobile apps and nobody owns them. Three vendors and one open-source option made the shortlist after a two-week trial on the checkout service.'],
  question:'Which error-monitoring tool do we standardise on for web, mobile and backend?',
  options:[{id:'beacon', name:'Beacon'},{id:'lumen', name:'Lumen'},{id:'trace', name:'Tracewell'},{id:'oss', name:'Self-hosted open source'}],
  chosen:'beacon', because:'it is the only option with EU data residency and mobile source maps out of the box, at a price within the observability budget.',
  attributes:[{name:'Pricing model', values:{beacon:'Per event, volume tiers', lumen:'Per seat', trace:'Per event', oss:'Infrastructure only'}},
    {name:'EU data residency', values:{beacon:'Yes, Frankfurt', lumen:'Yes, Dublin', trace:'US only', oss:'Yes, our cluster'}},
    {name:'Mobile source maps', values:{beacon:'Built in', lumen:'Plugin, beta', trace:'Built in', oss:'Manual upload'}, best:'beacon'},
    {name:'SSO and SCIM', values:{beacon:'Business plan', lumen:'All plans', trace:'Enterprise only', oss:'LDAP only'}, best:'lumen'},
    {name:'Data retention', values:{beacon:'90 days', lumen:'30 days', trace:'90 days', oss:'Unlimited'}, best:'oss'}],
  metrics:[{name:'Annual cost', unit:'$k', better:'low', values:{beacon:38, lumen:52, trace:29, oss:18}},{name:'Days to set up across all apps', unit:'days', better:'low', values:{beacon:3, lumen:2, trace:5, oss:15}}],
  criteria:[{id:'res', name:'EU data residency', weight:3},{id:'mob', name:'Mobile crash coverage', weight:2},{id:'cost', name:'Annual cost', weight:1}],
  ratings:{res:{beacon:2, lumen:2, trace:-2, oss:2}, mob:{beacon:2, lumen:0, trace:2, oss:-1}, cost:{beacon:0, lumen:-1, trace:1, oss:2}},
  risks:[{text:'Event volume doubles and the bill with it', likelihood:3, impact:3, mitigation:'Sample 20% of handled errors; spend alert at $3.5k/month'},
    {text:'Renewal price rises after year one', likelihood:3, impact:2, mitigation:'Negotiate a two-year price cap'},
    {text:'EU residency fails the security audit', likelihood:1, impact:5, mitigation:'Get the data-processing agreement reviewed before signing'},
    {text:'Teams keep the old alerts running in parallel', likelihood:4, impact:2, mitigation:'Switch off old alerts service by service'}],
  consequences:{good:['One place to see crashes across all apps'], bad:['$38k a year of new spend','Error data leaves our own infrastructure'], neutral:['Old alert scripts are retired']},
  people:{decided:['Dana Okafor'], consulted:['Security','Mobile leads'], informed:['All engineering']},
  advocate:{persona:'cfo', strength:'mixed', verdict:'The price comparison stops at year one. Per-event pricing is the line that grows, and the record has no ceiling on it.',
    challenges:[{type:'hidden_cost', title:'Per-event pricing scales with every bad deploy', why:'One noisy release can double monthly events. Without sampling or a hard cap, the $38k is a floor, not an estimate.'},
      {type:'missing_option', title:'Tracewell with an EU proxy was never priced', why:'It is $9k cheaper. If residency can be met with a relay, the main reason for Beacon weakens.'},
      {type:'weak_evidence', title:'Setup days come from a two-week trial on one service', why:'Mobile apps were not in the trial, so the 3-day estimate is untested where it matters most.'},
      {type:'question', title:'What does renewal look like in year two?', why:'Ask for a written price cap before signing; switching costs rise once every app ships the SDK.'}]}
};

S['build-vs-buy'] = {
  title:'Feature flags: build, buy or self-host', status:'accepted', date:'2026-09-02',
  context:['Flags live in environment variables, a database table and a hard-coded list. Releases wait on deploys to flip them.'],
  question:'Do we build a flag service, buy one, or run an open-source one?',
  options:[{id:'build', name:'Build in-house'},{id:'buy', name:'FlagKit (SaaS)'},{id:'oss', name:'Open source, self-hosted'}],
  chosen:'buy', because:'it is live this month with audit logs and targeting, while building takes a quarter and self-hosting adds an on-call service we do not have people for.',
  series:{name:'Cumulative cost', unit:'$k', better:'low', x:['M0','M3','M6','M9','M12','M15','M18','M21','M24'],
    values:{build:[60,72,84,96,108,120,132,144,156], buy:[8,26,44,64,86,110,136,164,194], oss:[30,45,60,75,90,105,120,135,150]}},
  attributes:[{name:'Time to first flag', values:{build:'10–12 weeks', buy:'1 week', oss:'3 weeks'}, best:'buy'},
    {name:'On-call burden', values:{build:'New service to run', buy:'None', oss:'New service to run'}, best:'buy'},
    {name:'Targeting rules', values:{build:'Whatever we build', buy:'Segments, percentages, schedules', oss:'Segments, percentages'}},
    {name:'Exit cost', values:{build:'—', buy:'SDK swap across 14 services', oss:'Low'}, best:'oss'}],
  assumptions:[{text:'Seat-based pricing stays under 400 seats through 2027', test:'Monthly seat report from finance', killIf:'More than 400 seats for two months running', status:'holding'},
    {text:'Teams flip flags without engineering help', test:'Count of flag changes by product managers', killIf:'Fewer than 20% of changes come from outside engineering after 3 months', status:'untested'}],
  timeline:[{when:'M0', what:'Sign a one-year contract', state:'done'},{when:'M1', what:'Move checkout and search to FlagKit', state:'now', gate:'No change in error rate'},{when:'M3', what:'Retire environment-variable flags'},{when:'M12', what:'Compare cost with self-hosting', gate:'Renew only if still cheaper or seats < 400'}],
  consequences:{good:['Flags flip in seconds without a deploy'], bad:['Cost grows with seats and passes self-hosting around M14'], neutral:[]},
  people:{decided:['Ana Ortiz'], consulted:['Platform team','Finance'], informed:['Product managers']}
};

S['product-bet'] = {
  title:'Fund team workspaces in Q1', status:'accepted', date:'2026-11-03',
  context:['Accounts with three or more active members churn at a third of the rate of solo accounts, yet only 14% of accounts ever invite anyone.'],
  question:'Which initiative gets the product team for Q1?',
  options:[{id:'ws', name:'Team workspaces'},{id:'offline', name:'Offline mode'},{id:'ai', name:'Smart summaries'},{id:'sso', name:'SSO for all plans'}],
  chosen:'ws', because:'it goes straight at the strongest retention signal we have, and the pilot can prove or kill it inside six weeks.',
  quadrant:{x:{name:'Effort', low:'days', high:'quarters', min:0, max:10}, y:{name:'Expected impact', low:'low', high:'high', min:0, max:10}, labels:['Quick wins','Big bets','Fill-ins','Money pits'],
    items:[{name:'Team workspaces', x:6.2, y:8.6, option:'ws'},{name:'Offline mode', x:8.3, y:5.8, option:'offline'},{name:'Smart summaries', x:4.4, y:6.2, option:'ai'},{name:'SSO for all plans', x:2.6, y:4.4, option:'sso'},{name:'Dark mode', x:1.6, y:2.2},{name:'PDF export', x:3.2, y:2.8},{name:'Public API', x:7.4, y:3.4}]},
  assumptions:[{text:'Teams of three or more churn less because of the team, not because they are bigger companies', test:'Compare churn within company-size bands', killIf:'The gap closes to under 5 points inside each band'},
    {text:'Invites are the bottleneck, not the value of collaborating', test:'Design-partner pilot with 30 accounts', killIf:'Pilot accounts add fewer than 1.5 members on average in six weeks'}],
  confirmation:[{metric:'Accounts with 3+ active members', target:'1,200', by:'end of Q1', how:'Weekly activation report'},{metric:'60-day churn, pilot vs control', target:'−8 pts', by:'week 10'}],
  timeline:[{when:'Jan', what:'Design-partner pilot, 30 accounts', gate:'Average 1.5 new members per account'},{when:'Feb', what:'Beta for 500 accounts'},{when:'Mar', what:'General release', gate:'Churn gap holds in the beta'}],
  consequences:{good:['Retention work has a clear owner'], bad:['Offline mode slips to Q3, which our field-sales customers asked for'], neutral:[]},
  people:{decided:['Lee Park'], consulted:['Sales','Design'], informed:['Company all-hands']}
};

S['migration'] = {
  title:'Move the payments database from MySQL 5.7 to PostgreSQL 16', status:'accepted', date:'2026-08-18',
  context:['MySQL 5.7 is out of support and our cloud provider will charge extended-support fees from February. The payments schema has 41 tables and 2.3 TB of data.'],
  question:'How do we move without downtime and with a tested way back?',
  options:[{id:'dual', name:'Dual writes, then cut over'},{id:'bigbang', name:'Weekend big-bang migration'},{id:'mysql8', name:'Upgrade to MySQL 8 instead'}],
  chosen:'dual', because:'it needs no downtime window, and every step until the final write switch can be rolled back in minutes.',
  timeline:[{when:'Wk 1–2', what:'Port the schema and start change-data capture', state:'done'},{when:'Wk 3–6', what:'Dual writes with shadow reads', state:'now', gate:'Zero row mismatches for 7 days'},
    {when:'Wk 7–8', what:'Move reads over, 5% → 100%', gate:'p99 query time under 40 ms'},{when:'Wk 9', what:'Stop writes to MySQL', gate:'Rollback drill passed'},{when:'Wk 12', what:'Decommission MySQL'}],
  risks:[{text:'Data drift between the two databases during dual writes', likelihood:3, impact:5, mitigation:'Nightly checksum job; pause the rollout on any mismatch'},
    {text:'ORM queries behave differently on PostgreSQL', likelihood:4, impact:3, mitigation:'Run the full suite against both in CI from week 1'},
    {text:'Rollback after the write switch fails', likelihood:2, impact:5, mitigation:'Keep reverse replication for 3 weeks and drill it'},
    {text:'Twelve weeks of double infrastructure cost', likelihood:4, impact:2, mitigation:'Budgeted: $9k'},
    {text:'Team fatigue on a long migration', likelihood:3, impact:2, mitigation:'Rotate the owner every three weeks'}],
  confirmation:[{metric:'Downtime during cutover', target:'0 min', by:'week 9'},{metric:'p99 payment query', target:'< 40 ms', by:'week 8'}],
  consequences:{good:['Off an unsupported database before fees start'], bad:['Twelve weeks of double running cost','Two people on the migration for a quarter'], neutral:[]},
  people:{decided:['Sam Chen'], consulted:['Payments team','DBA guild'], informed:['Finance']}
};

S['process-change'] = {
  title:'Replace per-team on-call with a central incident-commander rota', status:'proposed', date:'2026-10-27',
  context:['Every team runs its own on-call. Major incidents spanning several teams take 25 minutes on average before anyone is clearly in charge.'],
  question:'Who should lead an incident from the first page to the postmortem?',
  options:[{id:'now', name:'Per-team on-call (today)'},{id:'ic', name:'Central incident-commander rota'}],
  chosen:'ic', because:'one trained person takes charge within five minutes, and team on-call engineers fix things instead of coordinating.',
  attributes:[{name:'Who leads an incident', values:{now:'Whoever was paged first', ic:'The incident commander on the rota'}, best:'ic'},
    {name:'Pages per engineer a month', values:{now:'6.1', ic:'4.4 (estimate)'}, best:'ic'},
    {name:'Postmortem owner', values:{now:'Unclear', ic:'Incident commander'}, best:'ic'},
    {name:'Training needed', values:{now:'None', ic:'Two days per commander'}, best:'now'}],
  people:{decided:['Head of Engineering'], responsible:['SRE lead','8 volunteer commanders'], consulted:['Team leads','People team'], informed:['All engineering','Support']},
  assumptions:[{text:'Eight volunteers is enough for a sustainable rota', test:'Track hours on duty per commander', killIf:'Any commander is on duty more than one week in four', status:'untested'},
    {text:'Teams accept an outsider leading their incidents', test:'Survey after the first ten incidents', killIf:'Fewer than 60% of responders rate it better than before'}],
  consequences:{good:['Clear command within five minutes','Postmortems happen every time'], bad:['Two days of training per commander','A new rota to staff and pay for'], neutral:[]},
  confirmation:[{metric:'Time to an incident commander', target:'< 5 min', by:'end of Q1'},{metric:'Postmortems completed', target:'100%', by:'end of Q1'}]
};

root.BentoSamples = S;
})(typeof globalThis !== 'undefined' ? globalThis : this);
