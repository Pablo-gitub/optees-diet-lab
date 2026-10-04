"""Local Optees smoke audit across both diets and weeks, using demo targets."""
import asyncio
import json
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from optees_command import optees_command
from plan_diet_day import load_foods,formulate,decode_result
from daily_meals import defaults
from multiobjective_day import solve_strategy,nondominated
ROOT=Path(__file__).resolve().parents[1]

async def main():
    base=json.loads((ROOT/'config/demo-diet-day.json').read_text())
    base.update(daily_meals=defaults(True),food_preferences=json.loads((ROOT/'data/personal/current_food_preferences.json').read_text()))
    records=[]
    async with stdio_client(StdioServerParameters(command=optees_command(base))) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            for mode,day in [('sedentary',0),('sedentary',7),('training',0),('training',10)]:
                config=dict(base,mode=mode,day_index=day);foods=load_foods();p,c,slots=formulate(config,foods)
                for strategy in ['balanced','minmax','maxmin','pareto']:
                    results=[]
                    for weights in ([None,{'kcal':4},{'protein_g':4},{'fat_g':4},{'carbs_available_g':4}] if strategy=='pareto' else [None]):
                        result=await solve_strategy(session,p,config,c,strategy,weights)
                        record=decode_result(config,p,c,slots,foods,result)
                        assert record['status']=='optimal' and record['constraint_report']['all_respected'],(mode,day,strategy)
                        results.append(result)
                    selected=nondominated(results) if strategy=='pareto' else results
                    records.append(dict(mode=mode,day_index=day,strategy=strategy,candidates=len(selected),optimization=[r['optimization'] for r in selected]))
                    print(mode,day+1,strategy,'verified',len(selected),flush=True)
    (ROOT/'data/personal/multiobjective_audit.json').write_text(json.dumps(dict(scope='Representative modeled days, demo targets',records=records),indent=2)+'\n')

if __name__=='__main__':asyncio.run(main())
