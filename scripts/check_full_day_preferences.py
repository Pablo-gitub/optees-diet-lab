"""Repeat a demo-target audit of 28 modeled days with personal breakfast/snacks."""
import sys,json,asyncio,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
from optees_command import optees_command
from plan_diet_day import load_foods,formulate,optimize_day,decode_result
from daily_meals import defaults
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
 base=json.loads((root/'config/demo-diet-day.json').read_text());base['daily_meals']=defaults(True);base['food_preferences']=json.loads((root/'data/personal/current_food_preferences.json').read_text());records=[]
 async with stdio_client(StdioServerParameters(command=optees_command(base))) as (read,write):
  async with ClientSession(read,write) as session:
   await session.initialize()
   for mode in ['sedentary','training']:
    for day in range(14):
     config=dict(base,mode=mode,day_index=day);foods=load_foods();p,c,slots=formulate(config,foods);result=await optimize_day(session,p);record=decode_result(config,p,c,slots,foods,result);record['mode']=mode;record['day_index']=day;records.append(record)
     print(mode,day+1,record['status'],record['preference_penalty'],flush=True)
 path=root/'data/personal/full_day_preferences_audit.json';path.write_text(json.dumps(dict(scope='Personalized breakfast/snacks; demo whole-day targets, modeled lunch/dinner, not complete source diet or weekly frequency validation',source_hashes={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [root/'scripts/plan_diet_day.py',root/'scripts/daily_meals.py',root/'dataset/crea/foods.csv',root/'data/personal/current_food_preferences.json',root/'data/personal/diet_combination_rules.json',root/'data/personal/ocr/sedentary/schedule_visual_checked.json',root/'data/personal/ocr/training/schedule_visual_checked.json']},records=records),ensure_ascii=False,indent=2)+'\n')
 print({m:sum(r['status']=='optimal' for r in records if r['mode']==m) for m in ['sedentary','training']})
asyncio.run(main())
