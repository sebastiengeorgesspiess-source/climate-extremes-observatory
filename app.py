#!/usr/bin/env python3
import csv, io, json, os, statistics, threading, hashlib, math
from datetime import datetime, timezone
from pathlib import Path
import requests
from flask import Flask, jsonify, render_template, request, Response

BASE=Path(__file__).resolve().parent; CACHE=BASE/'data'/'earth-system.json'; lock=threading.Lock(); app=Flask(__name__)
COUNTRY_CACHE=BASE/'data'/'countries'; CCKP='https://cckpapi.worldbank.org/api/v1'
COUNTRY_TTL=7*86400
country_refreshing=set(); country_guard=threading.Lock(); country_attempts={}
UA={'User-Agent':'Sebastien-Spiess-Earth-System-Observatory/1.0'}
SOURCES={
 'temperature':'https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv',
 'co2':'https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.csv',
 'sea_ice':'https://noaadata.apps.nsidc.org/NOAA/G02135/north/monthly/data/N_09_extent_v4.0.csv',
 'ocean_heat':'https://www.ncei.noaa.gov/data/oceans/woa/DATA_ANALYSIS/3M_HEAT_CONTENT/DATA/basin/yearly/h22-w0-2000m.dat'}

def text(url,timeout=70):
 r=requests.get(url,headers=UA,timeout=timeout); r.raise_for_status(); return r.text

def temperature():
 raw=text(SOURCES['temperature']).splitlines(); rows=list(csv.DictReader(io.StringIO('\n'.join(raw[1:])))); out=[]
 for r in rows:
  try: out.append({'year':int(r['Year']),'value':float(r['J-D'])})
  except: pass
 return out

def co2():
 out=[]
 for r in csv.reader(x for x in text(SOURCES['co2']).splitlines() if not x.startswith('#')):
  try: out.append({'year':int(r[0]),'value':float(r[1]),'uncertainty':float(r[2])})
  except: pass
 return out

def sea_ice():
 rows=csv.DictReader(io.StringIO(text(SOURCES['sea_ice']))); out=[]
 today=datetime.now(timezone.utc)
 for raw in rows:
  try:
   r={k.strip().lower():v for k,v in raw.items()}; y,m,v=int(r['year']),int(r['mo']),float(r['extent'])
   if m==9 and math.isfinite(v) and v>=0 and (y<today.year or (y==today.year and today.month>9)):
    out.append({'year':y,'value':round(v,3)})
  except (ValueError,KeyError,TypeError): pass
 if not out: raise ValueError('No completed September monthly values returned')
 return sorted(out,key=lambda x:x['year'])

def age_seconds(stamp):
 try: return max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(stamp.replace('Z','+00:00'))).total_seconds())
 except (ValueError,TypeError,AttributeError): return float('inf')

def country_background(iso):
 try: country_profile(iso,force=True)
 except Exception: app.logger.warning('Country refresh failed for %s; existing data retained',iso)
 finally:
  with country_guard: country_refreshing.discard(iso)

def ocean_heat():
 out=[]
 for line in text(SOURCES['ocean_heat']).splitlines()[1:]:
  p=line.split()
  try: out.append({'year':int(float(p[0])),'value':float(p[1]),'uncertainty':float(p[2])})
  except: pass
 return out

def regional_intelligence():
 hfo=get_json_local('http://127.0.0.1:8091/api/data')
 health=get_json_local('http://127.0.0.1:8092/api/data')
 lookup={c['iso3']:c for c in health.get('countries',[])}
 rows=[]
 for iso,record in hfo.get('heat',{}).get('countries',{}).items():
  geo=lookup.get(iso); pop=hfo.get('population',{}).get('countries',{}).get(iso,{})
  if not geo: continue
  mid=record['scenarios']['ssp245']['2040-2059']; high=record['scenarios']['ssp585']['2080-2099']
  population=pop.get('timeline',{}).get('2050',{}).get('Medium')
  rows.append({'iso3':iso,'name':geo['name'],'region':geo['region'],'lat':geo['lat'],'lon':geo['lon'],'heat_2050':mid['median'],'heat_2050_p10':mid['p10'],'heat_2050_p90':mid['p90'],'heat_2100_high':high['median'],'population_2050_m':population})
 rows.sort(key=lambda x:x['heat_2100_high'],reverse=True)
 regions={}
 for row in rows:
  regions.setdefault(row['region'],[]).append(row)
 region_rows=[]
 for name,items in regions.items():
  region_rows.append({'name':name,'countries':len(items),'heat_2050':round(statistics.mean(x['heat_2050'] for x in items),1),'heat_2100_high':round(statistics.mean(x['heat_2100_high'] for x in items),1)})
 region_rows.sort(key=lambda x:x['heat_2100_high'],reverse=True)
 return rows,region_rows

def get_json_local(url):
 r=requests.get(url,timeout=45,headers=UA);r.raise_for_status();return r.json()

def cckp(url):
 r=requests.get(url,timeout=90,headers=UA); r.raise_for_status()
 payload=r.json().get('data',{})
 return payload

VARIABLES={
 'tas':('Mean temperature','°C'), 'hd30':('Hot days above 30°C','days/year'),
 'pr':('Mean precipitation','mm/day'), 'rx1day':('Maximum 1-day precipitation','mm'),
 'cdd':('Maximum consecutive dry days','days'), 'fd':('Frost days','days/year')}
PERIODS={'2030':'2020-2039','2050':'2040-2059','2100':'2080-2099'}
SCENARIOS=['ssp126','ssp245','ssp585']
LARGE_COUNTRIES={'ARG','AUS','BRA','CAN','CHN','COD','DZA','IND','IDN','KAZ','MEX','MNG','RUS','SAU','USA'}

def unwrap_country(payload,iso):
 node=payload.get(iso,{}) if isinstance(payload,dict) else {}
 return node if isinstance(node,dict) else {}

def observed_series(iso,var):
 slug=f'era5-x0.25_timeseries_{var}_timeseries_annual_1950-2025_mean_historical_era5_x0.25_mean'
 url=f'{CCKP}/{slug}/{iso}?_format=json'
 raw=unwrap_country(cckp(url),iso); out=[]
 for key,val in raw.items():
  try: out.append({'year':int(str(key)[:4]),'value':round(float(val),3)})
  except (TypeError,ValueError): pass
 out.sort(key=lambda x:x['year'])
 return {'series':out,'source_url':url}

def observed_all(iso):
 names=','.join(VARIABLES); slug=f'era5-x0.25_timeseries_{names}_timeseries_annual_1950-2025_mean_historical_era5_x0.25_mean'; url=f'{CCKP}/{slug}/{iso}?_format=json'
 raw=cckp(url); result={}
 for var in VARIABLES:
  node=unwrap_country(raw.get(var,{}) if isinstance(raw,dict) else {},iso); rows=[]
  for key,val in node.items():
   try: rows.append({'year':int(str(key)[:4]),'value':round(float(val),3)})
   except (TypeError,ValueError): pass
  result[var]=sorted(rows,key=lambda x:x['year'])
 return result,url

def projection_point(iso,var,period,scenario,percentile):
 slug=f'cmip6-x0.25_climatology_{var}_anomaly_annual_{period}_{percentile}_{scenario}_ensemble_all_mean'
 url=f'{CCKP}/{slug}/{iso}?_format=json'
 raw=unwrap_country(cckp(url),iso)
 values=[]
 for val in raw.values():
  try: values.append(float(val))
  except (TypeError,ValueError): pass
 return (round(statistics.mean(values),3) if values else None),url

def projection_all(iso,period,scenario,percentile):
 names=','.join(VARIABLES); slug=f'cmip6-x0.25_climatology_{names}_anomaly_annual_{period}_{percentile}_{scenario}_ensemble_all_mean'; url=f'{CCKP}/{slug}/{iso}?_format=json'
 raw=cckp(url); result={}
 for var in VARIABLES:
  node=unwrap_country(raw.get(var,{}) if isinstance(raw,dict) else {},iso); vals=[]
  for value in node.values():
   try: vals.append(float(value))
   except (TypeError,ValueError): pass
  result[var]=round(statistics.mean(vals),3) if vals else None
 return result,url

def glacier_profile(iso):
 slug='nasa-pygem-oggm-x0.25_timeseries_area,glaciercount,mass_anomalypercent_annual_2000-2100_median,p10,p90_ssp126,ssp245,ssp585_ensemble_all_mean'
 url=f'{CCKP}/{slug}/{iso}?_format=json'; raw=cckp(url); result={}
 for var in ('area','glaciercount','mass'):
  result[var]={}
  for scenario in SCENARIOS:
   result[var][scenario]={}
   for year in PERIODS:
    point={}
    for pct in ('p10','median','p90'):
     node=raw.get(var,{}).get(pct,{}).get(scenario,{}).get(iso,{}) if isinstance(raw,dict) else {}
     value=next((v for k,v in node.items() if str(k).startswith(year)),None)
     try: point[pct]=round(float(value),2)
     except (TypeError,ValueError): point[pct]=None
    result[var][scenario][year]=point
 available=any(result['area'][s][y]['median'] is not None for s in SCENARIOS for y in PERIODS)
 return ({'available':available,'reference_year':2000,'unit':'Index: year 2000 = 100','interpretation':'Source returns 100 for the reference year. A value of 50 means half of the reference-year quantity remains; do not add 100 to these values.','variables':result,'source_url':url} if available else {'available':False,'source_url':url})

def subnational_profile(iso):
 if iso not in LARGE_COUNTRIES:return {'available':False,'reason':'ADM1 comparison is enabled for geographically large states.'}
 slug='era5-x0.25_timeseries_tas_timeseries_annual_1950-2025_mean_historical_era5_x0.25_mean'; url=f'{CCKP}/{slug}/{iso}.@?_format=json'; raw=cckp(url); values=[]
 for adm1,series in raw.items():
  if not isinstance(series,dict):continue
  base=[]; recent=[]
  for key,value in series.items():
   try:
    year=int(str(key)[:4]); val=float(value)
    if 1991<=year<=2020:base.append(val)
    if 2015<=year<=2025:recent.append(val)
   except (TypeError,ValueError):pass
  if base and recent:values.append({'id':adm1,'anomaly_c':round(statistics.mean(recent)-statistics.mean(base),2)})
 if not values:return {'available':False,'source_url':url}
 anomalies=sorted(v['anomaly_c'] for v in values)
 return {'available':True,'units':len(values),'metric':'2015–2025 mean temperature minus 1991–2020 mean','unit':'°C','minimum':anomalies[0],'median':round(statistics.median(anomalies),2),'maximum':anomalies[-1],'spread':round(anomalies[-1]-anomalies[0],2),'source_url':url,'note':'ADM1 identifiers and aggregations are supplied by CCKP. The range demonstrates within-country variation; it is not a local forecast.'}

def country_profile(iso,force=False):
 iso=iso.upper(); allowed={x['iso3']:x for x in load().get('countries',[])}
 if iso not in allowed: raise ValueError('Unknown country code')
 path=COUNTRY_CACHE/f'{iso}.json'
 if path.exists() and not force:
  cached=json.loads(path.read_text(encoding='utf-8')); stale=age_seconds(cached.get('generated_at'))>COUNTRY_TTL
  if stale:
   with country_guard:
    if iso not in country_refreshing and age_seconds(country_attempts.get(iso))>3600:
     country_refreshing.add(iso); country_attempts[iso]=datetime.now(timezone.utc).isoformat()
     threading.Thread(target=country_background,args=(iso,),daemon=True).start()
  return cached
 country=allowed[iso]; evidence=[]
 try: observed,url=observed_all(iso); evidence.append(url)
 except Exception: observed={var:[] for var in VARIABLES}
 projections={var:{scenario:{year:{pct:None for pct in ('p10','median','p90')} for year in PERIODS} for scenario in SCENARIOS} for var in VARIABLES}
 for scenario in SCENARIOS:
  for year,period in PERIODS.items():
   for pct in ('p10','median','p90'):
    try:
     values,url=projection_all(iso,period,scenario,pct); evidence.append(url)
     for var,value in values.items(): projections[var][scenario][year][pct]=value
    except Exception: pass
 try: glacier=glacier_profile(iso); evidence.append(glacier['source_url'])
 except Exception: glacier={'available':False}
 try: subnational=subnational_profile(iso); evidence.extend([subnational['source_url']] if subnational.get('source_url') else [])
 except Exception: subnational={'available':False}
 tas=observed.get('tas',[]); baseline=[x['value'] for x in tas if 1991<=x['year']<=2020]
 recent=[x['value'] for x in tas if 2015<=x['year']<=2025]
 warming=round(statistics.mean(recent)-statistics.mean(baseline),2) if baseline and recent else None
 brief=f"{country['name']} has warmed relative to the 1991–2020 reference" if warming is not None and warming>0 else f"Observed warming for {country['name']} is evaluated against 1991–2020"
 brief+=('. Under higher-emission pathways, physical climate indicators diverge increasingly towards 2100. These are scenario-conditioned projections, not forecasts.')
 profile={'generated_at':datetime.now(timezone.utc).isoformat(),'iso3':iso,'name':country['name'],'region':country['region'],
  'reference_period':'1991–2020','projection_reference_period':'1995–2014','observed_recent_anomaly_c':warming,'observed':observed,'projections':projections,
  'variables':{k:{'label':v[0],'unit':v[1]} for k,v in VARIABLES.items()},'periods':PERIODS,'scenarios':SCENARIOS,'brief':brief,
  'glacier':glacier,'subnational':subnational,'conditional_sections':{'coast':'Coastal projections need a separate marine-area identifier (EEZ: exclusive economic zone). Land averages cannot substitute for coastal data.','snow':'Frost days do not measure snow depth or how long snow remains on the ground. These snow indicators are not available here.'},
  'method':'Historical country averages use ERA5: weather observations combined with a physical model. Future changes use CMIP6 climate models and compare 20-year periods with 1995–2014. The middle value is the median; P10–P90 describes model spread, not an 80% guarantee. No combined risk score is calculated.',
  'evidence':{'publisher':'World Bank Climate Change Knowledge Portal','datasets':['ERA5 0.25° · DOI 10.57966/128g-6s70','Bias-corrected CMIP6 0.25°','NASA PyGEM-OGGM V001 · DOI 10.5067/P8BN9VO9N5C7'],'license':'CCKP Terms of Use; source-dataset terms apply','spatial_resolution':'0.25° area-weighted country aggregate','temporal_coverage':'1950–2025 observed; 2000–2100 glacier; 2020–2099 climate projections','transformations':['annual country aggregation supplied by CCKP','scenario-period ensemble extraction','no interpolation','no composite score'],'missing_values':'Retained as null; never imputed','update_rhythm':'On-demand cache refresh','accessed':datetime.now(timezone.utc).date().isoformat(),'urls':sorted(set(evidence))}}
 profile['evidence']['update_rhythm']='Automatically renewed on the next visit after seven days; cached data remain visible during renewal.'
 if not any(observed.values()): raise ValueError('Observed country data unavailable; existing profile retained')
 if path.exists():
  old=json.loads(path.read_text(encoding='utf-8'))
  old_count=sum(x[p] is not None for v in old.get('projections',{}).values() for s in v.values() for x in s.values() for p in ('p10','median','p90'))
  new_count=sum(x[p] is not None for v in projections.values() for s in v.values() for x in s.values() for p in ('p10','median','p90'))
  if new_count<old_count: raise ValueError('Incomplete projection refresh; existing profile retained')
 canonical=json.dumps(profile,sort_keys=True,separators=(',',':')).encode(); profile['evidence']['artifact_sha256']=hashlib.sha256(canonical).hexdigest()
 COUNTRY_CACHE.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(profile),encoding='utf-8'); os.replace(tmp,path)
 return profile

def climate_relevant_events():
 try:
  payload=get_json_local('http://127.0.0.1:5000/api/anomalies?continent=Global')
  allowed={'wildfire','storm','weather'}
  events=[{'name':x.get('name'),'type':x.get('type'),'lat':x.get('lat'),'lon':x.get('lon'),'detail':x.get('detail'),'attribution':'Not assessed'} for x in payload.get('events',[]) if x.get('type') in allowed and x.get('lat') is not None][:500]
  return {'updated_at':payload.get('last_update'),'events':events,'note':'Detected hazard signals are not automatically attributable to climate change. Event attribution requires a dedicated peer-reviewed analysis.'}
 except Exception as e:return {'updated_at':None,'events':[],'note':'Operational hazard feed temporarily unavailable; no events inferred.'}

def rank(series,reverse=True):
 vals=sorted((x['value'] for x in series),reverse=reverse); return vals.index(series[-1]['value'])+1

def build():
 previous=json.loads(CACHE.read_text()) if CACHE.exists() else {}; series={}; source_status={}
 for key,fetcher in [('temperature',temperature),('co2',co2),('sea_ice',sea_ice),('ocean_heat',ocean_heat)]:
  try:
   values=fetcher()
   if not values or any(not math.isfinite(x['value']) for x in values): raise ValueError('Invalid source values')
   series[key]=values; source_status[key]={'last_success':datetime.now(timezone.utc).isoformat(),'status':'ok','url':SOURCES[key]}
  except Exception:
   if not previous.get('series',{}).get(key): raise
   series[key]=previous['series'][key]
   source_status[key]={'last_success':previous.get('source_status',{}).get(key,{}).get('last_success',previous.get('generated_at')),'status':'cached','url':SOURCES[key]}
 countries,regions=regional_intelligence(); events=climate_relevant_events()
 latest={k:v[-1] for k,v in series.items()}
 baseline=[x['value'] for x in series['temperature'] if 1951<=x['year']<=1980]
 latest['temperature']['baseline_note']='NASA anomaly relative to 1951–1980'; latest['temperature']['rank']=rank(series['temperature'])
 latest['co2']['rank']=rank(series['co2']); latest['sea_ice']['rank']=rank(series['sea_ice'],False); latest['ocean_heat']['rank']=rank(series['ocean_heat'])
 return {'generated_at':datetime.now(timezone.utc).isoformat(),'source_status':source_status,'series':series,'latest':latest,'baseline_mean':round(statistics.mean(baseline),3),'countries':countries,'regions':regions,'events':events,'outlook':{
  'sea_level_2050':{'low':0.15,'high':0.29,'unit':'m','baseline':'1995–2014','range_type':'likely ranges across SSP1–1.9 to SSP5–8.5'},
  'sea_level_2100_low':{'median':0.38,'low':0.28,'high':0.55,'scenario':'SSP1–1.9'},
  'sea_level_2100_high':{'median':0.77,'low':0.63,'high':1.01,'scenario':'SSP5–8.5'},
  'glacier_2024_loss_gt':450,'glacier_2024_balance_mwe':-1.3,'countries_all_glaciers_lost':['Slovenia','Venezuela'],
  'glacier_remaining_warming':'About 50–60% of present glacier mass remains at sustained 1.5–2°C warming, excluding ice sheets and Antarctic peripheral glaciers.',
  'arctic':'The Arctic is likely to have at least one effectively ice-free September before 2050, across the assessed scenarios. Effectively ice-free means less than one million square kilometres of sea ice, not zero ice.'},'sources':[
  {'name':'NASA GISTEMP v4','measure':'Global land–ocean temperature anomaly','url':'https://data.giss.nasa.gov/gistemp/'},
  {'name':'NOAA Global Monitoring Laboratory','measure':'Mauna Loa annual mean atmospheric CO₂','url':'https://gml.noaa.gov/ccgg/trends/'},
  {'name':'NSIDC Sea Ice Index v4','measure':'September Arctic sea-ice extent','url':'https://nsidc.org/data/g02135/versions/4'},
  {'name':'NOAA NCEI Ocean Heat Content','measure':'Global 0–2,000 m ocean heat-content anomaly','url':'https://www.ncei.noaa.gov/products/climate-data-records/global-ocean-heat-content'},
  {'name':'IPCC AR6 WGI','measure':'Sea level, cryosphere and assessed future ranges','url':'https://www.ipcc.ch/report/ar6/wg1/'},
  {'name':'WMO State of the Global Climate','measure':'Glacier loss, ocean and extreme-event synthesis','url':'https://public.wmo.int/publication-series/state-of-global-climate/state-of-global-climate-2025'},
  {'name':'Zenodo release 2.0.0','measure':'Archived source, methods, manifest and independent-review protocol · DOI 10.5281/zenodo.22175808','url':'https://doi.org/10.5281/zenodo.22175808'},
  {'name':'HFO CMIP6 ensemble','measure':'Country heat-day projections with p10–p90 spread','url':'/hfo/'}],
  'method_note':'Observed annual indicators retain their native baselines, units and uncertainty fields. They are not combined into a score. Co-movement is not proof of causation.'}

def refresh():
 with lock:
  p=build(); CACHE.parent.mkdir(parents=True,exist_ok=True); tmp=CACHE.with_suffix('.tmp'); tmp.write_text(json.dumps(p),encoding='utf-8'); os.replace(tmp,CACHE); return p
def load(): return json.loads(CACHE.read_text()) if CACHE.exists() else refresh()
@app.get('/')
def index():
 return render_template('intelligence.html')
@app.get('/api/data')
def data(): return jsonify(load())
@app.get('/api/health')
def health():
 p=load(); stale=age_seconds(p.get('generated_at'))>48*3600; degraded=stale or any(x.get('status')!='ok' for x in p.get('source_status',{}).values())
 return jsonify(status='degraded' if degraded else 'ok',updated_at=p['generated_at'],stale=stale,source_status=p.get('source_status',{}),series=len(p['series']))
@app.post('/api/refresh')
def api_refresh():
 try:return jsonify(refresh())
 except Exception as e:return jsonify(status='degraded',error=str(e),cached=CACHE.exists()),502
@app.get('/api/export.json')
def export():return jsonify(load())
@app.get('/api/country/<iso>')
def api_country(iso):
 try:return jsonify(country_profile(iso,request.args.get('refresh')=='1'))
 except ValueError as e:return jsonify(error=str(e)),404
 except Exception as e:return jsonify(error='Country data temporarily unavailable',detail=str(e)),502
@app.get('/api/country/<iso>/export.json')
def country_json(iso): return jsonify(country_profile(iso))
@app.get('/api/country/<iso>/export.csv')
def country_csv(iso):
 p=country_profile(iso); out=io.StringIO(); w=csv.writer(out); w.writerow(['iso3','country','evidence_type','variable','scenario','period','percentile','year','value','unit'])
 for var,rows in p['observed'].items():
  for row in rows:w.writerow([p['iso3'],p['name'],'observed ERA5',var,'historical','','mean',row['year'],row['value'],p['variables'][var]['unit']])
 for var,scenarios in p['projections'].items():
  for scenario,years in scenarios.items():
   for year,vals in years.items():
    for pct,value in vals.items():w.writerow([p['iso3'],p['name'],'projected CMIP6 anomaly',var,scenario,p['periods'][year],pct,year,value,p['variables'][var]['unit']])
 return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename=climate-{iso.upper()}.csv'})
@app.get('/api/country/<iso>/citation.bib')
def citation_bib(iso):
 p=country_profile(iso); key='SpiessClimate'+iso.upper()+datetime.now().strftime('%Y')
 bib=f'@dataset{{{key},\n  author = {{Spiess, Sebastien}},\n  title = {{{p["name"]} Climate Profile}},\n  year = {{{datetime.now().year}}},\n  url = {{https://sebastienspiess.ch/climate/}},\n  note = {{ERA5, bias-corrected CMIP6 and NASA PyGEM-OGGM data via World Bank CCKP; accessed {p["evidence"]["accessed"]}}}\n}}\n'
 return Response(bib,mimetype='application/x-bibtex',headers={'Content-Disposition':f'attachment; filename=climate-{iso.upper()}.bib'})
@app.get('/api/changelog')
def changelog(): return jsonify(version='2.1.0',released='2026-09-10',changes=['Reader-friendly terminology and emissions-pathway explanations','IPCC very-likely temperature ranges labelled as 2081–2100 averages','Official completed-September sea-ice series from 1979','Independent global-source fallback and retrieval-status metadata','Country cache renews in the background after seven days, preserving prior data if refresh fails','Country projection baseline explicitly 1995–2014; historical chart axes and annual data table','Glacier source index verified: year 2000 equals 100','Sea-level export ranges aligned with the published assessment','Print/PDF control removed from this dashboard; data downloads retained'])
if __name__=='__main__':app.run(host='127.0.0.1',port=8093)
