"""Printable, owner-only applied week. Local ReportLab, no external resources."""
import io
import json
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from html import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
import diary_service as diary
from shopping_list import read_week, shopping_list

SLOTS={'breakfast':'Colazione','morning_snack':'Spuntino mattutino','lunch':'Pranzo','afternoon_snack':'Spuntino pomeridiano','dinner':'Cena'}
LABELS={'kcal':'kcal','protein_g':'Proteine','fat_g':'Grassi','carbs_available_g':'Carboidrati'}


def number(value):
    return 'Non disponibile' if value is None else f'{float(value):.1f}'.replace('.',',')


def render(db,user,profile,start,include_all=False,today=None):
    _,days=read_week(db,user,profile,start)
    shop=shopping_list(db,user,profile,start,include_all,today)
    summary=diary.week_view(db,user,profile,start)
    font_dir=Path('/usr/share/fonts/truetype/dejavu')
    pdfmetrics.registerFont(TTFont('WeekText',str(font_dir/'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('WeekBold',str(font_dir/'DejaVuSans-Bold.ttf')))
    buffer=io.BytesIO();styles=getSampleStyleSheet()
    for key in styles.byName:styles[key].fontName='WeekBold' if key.startswith(('Heading','Title')) else 'WeekText'
    styles.add(ParagraphStyle(name='Food',fontName='WeekText',fontSize=10,leading=14,spaceAfter=4))
    story=[]
    def p(text,style='Food'):return Paragraph(escape(str(text)),styles[style])
    def heading(text):story.append(p(text,'Heading2'))
    def line(text):story.append(p(text))
    def table(rows,widths=None):
        values=[[p(c) for c in row] for row in rows]
        tab=Table(values,colWidths=widths,repeatRows=1,hAlign='LEFT')
        tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eef2')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#9eaeb8'))]))
        story.append(tab)
    line('PIANO SETTIMANALE PERSONALE')
    story.append(Spacer(1,18));story.append(p('Settimana del '+start,'Title'))
    line('Pasti, allenamento, attività e lista della spesa dalla settimana applicata.')
    heading('Obiettivi giornalieri')
    targets=days[0]['targets']
    table([['Nutriente','Bersaglio','Intervallo']]+[[LABELS.get(k,k),number(v['target']),number(v['min'])+' – '+number(v['max'])] for k,v in targets.items()],[200,110,180])
    heading('Bilancio della settimana')
    for key,label in [('kcal_target','Obiettivo energetico'),('kcal_planned','Energia pianificata'),('kcal_eaten','Energia registrata'),('kcal_remaining_planned','Energia ancora pianificata')]:line(label+': '+number(summary['budget'][key])+' kcal')
    line('Le quantità degli ingredienti sono riferite ai pesi indicati nel piano. Un dato mancante resta non disponibile.')
    for view in days:
        story.append(PageBreak());story.append(p('Giornata del '+view['date'],'Title'))
        for meal in view['meals']:
            heading(SLOTS.get(meal['slot'],meal['slot']))
            if not meal['planned']:line('Nessun pasto pianificato.');continue
            rows=[['Alimento','Quantità']]
            for item in meal['planned']['items']:
                rows.append([item['name'],'Stima a intervallo' if item['food']['source']=='dish_estimate' else number(item['grams'])+' g'])
                if item['food']['source']=='recipe':
                    recipe=profile.get('_recipe_runs',{}).get(item['food']['id'])
                    if recipe:
                        mass=sum(part['grams'] for part in recipe['selections'])
                        rows.extend([['  '+(part.get('food') or part['ingredient']),number(part['grams']*item['grams']/mass)+' g'] for part in recipe['selections']])
                        rows.extend([['  '+part['name'],'in traccia'] for part in recipe.get('trace_condiments',[])])
            table(rows,[365,125])
            interval=meal['planned'].get('nutrient_ranges')
            if interval:line('Stima: '+' | '.join(LABELS[k]+': '+number(interval[k]['min'])+' – '+number(interval[k]['max']) for k in LABELS))
            line('Stato del diario: '+{'unknown':'da registrare','as_planned':'consumato come previsto','modified':'consumato con modifiche','skipped':'saltato'}.get(meal['state'],meal['state']))
        heading('Obiettivi e nutrienti della giornata')
        line('Obiettivi: '+' | '.join(LABELS.get(k,k)+': '+number(v['target']) for k,v in view['targets'].items()))
        totals=view['totals']['planned'] or {}
        line(' | '.join(LABELS[k]+': '+number(totals.get(k))+(' kcal' if k=='kcal' else ' g') for k in LABELS))
        heading('Allenamenti e attività pianificati')
        rows=db.execute('SELECT s.* FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE w.user_id=? AND w.status=\'active\' AND s.date=? ORDER BY s.id',(user,view['date'])).fetchall()
        if not rows:line('Nessuna sessione pianificata.')
        for row in rows:
            session=json.loads(row['snapshot']);line(session['name']+' — '+number(session['duration_seconds']/60)+' minuti'+(' — ore '+row['start_time'] if row['start_time'] else ''))
            for exercise in (session.get('exercises',[]) if session.get('kind')!='activity' else []):
                sets=exercise.get('sets',[])
                if isinstance(sets,list):
                    specs=[]
                    for item in sets:
                        specs.append(str(item.get('reps',item.get('duration_seconds','—')))+(' rip.' if item.get('reps') else ' s')+' / '+number(item.get('load_kg'))+' kg')
                    detail=str(len(sets))+' serie: '+', '.join(specs)
                else:detail=str(sets)+' serie × '+str(exercise.get('repetitions','—'))+' rip.; '+number(exercise.get('load_kg'))+' kg'
                line((exercise.get('name_it') or exercise.get('name') or exercise.get('exercise_id','Esercizio'))+': '+detail)
    story.append(PageBreak());story.append(p('Riepilogo e lista della spesa','Title'))
    line('Allenamenti e attività pianificati: '+str(sum(len(d.get('workouts',[])) for d in days))+'; completati: '+str(sum(s['status']=='done' for d in days for s in d.get('workouts',[]))))
    line('Giornate con tutti i pasti registrati: '+str(summary['budget']['complete_days'])+' / 7')
    line('Energia pianificata: '+number(summary['budget']['kcal_planned'])+' kcal; registrata: '+number(summary['budget']['kcal_eaten'])+' kcal.')
    line('Lista: '+('intera settimana applicata' if include_all else 'pasti futuri ancora da consumare')+'. Data di riferimento: '+shop['as_of'])
    for dep in dict.fromkeys(i['department'] for i in shop['items']):
        heading(dep)
        rows=[['Alimento / prodotto','Totale','Confezioni']]
        for item in shop['items']:
            if item['department']==dep:rows.append([item['product_name']+(' ('+item['brand']+')' if item['brand'] else ''),number(item['grams'])+' g',str(item['packages'])+' × '+number(item['package_g'])+' g' if item['packages'] else 'Non disponibili'])
        table(rows,[290,90,110])
    if shop['trace_condiments']:
        heading('Condimenti in traccia');line(', '.join(i['name'] for i in shop['trace_condiments'])+' — quantità non ponderale.')
    for warning in shop['warnings']:line(warning)
    for item in shop['unresolved']:line('Composizione non disponibile: '+item['food']['id'])
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('WeekText',9);canvas.setFillColor(colors.HexColor('#58636b'));canvas.drawString(40,25,'Settimana '+start);canvas.drawRightString(A4[0]-40,25,'Pagina '+str(doc.page));canvas.restoreState()
    SimpleDocTemplate(buffer,pagesize=A4,rightMargin=40,leftMargin=40,topMargin=42,bottomMargin=42,title='Piano settimanale '+start,author='Pianificatore locale').build(story,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()
