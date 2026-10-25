import logging
import io
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

TOKEN = '8948110705:AAGnc6Rh_JClbxGBI32dUMx1dpVVP-64r7c'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏥 *Bot de Auditoría Concurrente - DIAGNOSTICO ADAX*\n\n"
        "¡Hola Angela! Envíame tu censo en `.xlsx` para depurar las columnas y calcular las métricas reales.",
        parse_mode='Markdown'
    )

async def procesar_censo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    documento = update.message.document
    if not documento or not documento.file_name.endswith(('.xlsx', '.xls')):
        await update.message.reply_text("❌ Por favor envía un archivo de Excel válido (.xlsx).")
        return

    await update.message.reply_text("⏳ Leyendo estructura real del Excel...")

    try:
        file = await context.bot.get_file(documento.file_id)
        file_bytes = await file.download_as_bytearray()
        
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)
        
        # Guardar nombres originales y limpiar
        columnas_originales = list(df.columns)
        df.columns = df.columns.str.strip().str.upper()
        total_pacientes = len(df)

        # Enviar las columnas detectadas para diagnóstico visual
        cols_str = ", ".join([str(c) for c in columnas_originales[:10]])
        await update.message.reply_text(f"🔍 *Columnas detectadas:* {cols_str}", parse_mode='Markdown')

        # Identificar columnas por posición o contenido flexible
        col_cama = df.columns[0]
        col_paciente = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        col_eps = df.columns[2] if len(df.columns) > 2 else df.columns[0]
        
        # Buscar columnas clave buscando coincidencias amplias
        col_servicio = next((c for c in df.columns if 'SERV' in c or 'UBIC' in c or 'AREA' in c or 'PAST' in c), df.columns[3] if len(df.columns) > 3 else None)
        col_esp = next((c for c in df.columns if 'ESP' in c or 'MED' in c or 'TRAT' in c), None)
        col_dias = next((c for c in df.columns if 'DIA' in c or 'EST' in c or 'TRAN' in c), None)
        col_dx = next((c for c in df.columns if 'DIAG' in c or 'DX' in c or 'PAT' in c), None)

        # Normalizar para filtros
        df['SRV'] = df[col_servicio].astype(str).str.lower() if col_servicio else ''
        df['ESP'] = df[col_esp].astype(str).str.lower() if col_esp else ''
        
        if col_dias:
            df['DIAS_NUM'] = pd.to_numeric(df[col_dias], errors='coerce').fillna(0)
        else:
            df['DIAS_NUM'] = 0

        # --- FILTROS DE ESTANCIA ---
        urgencias = df[df['SRV'].str.contains('urg', na=False)]
        hosp = df[df['SRV'].str.contains('hosp', na=False)]
        uci = df[df['SRV'].str.contains('uci', na=False)]

        urg_criticos = urgencias[urgencias['DIAS_NUM'] >= 3]
        hosp_criticos = hosp[hosp['DIAS_NUM'] >= 8]
        uci_criticos = uci[uci['DIAS_NUM'] >= 8]

        # 1. Reporte Global
        msg = f"📊 *INFORME CONCURRENTE ADAX*\n\n"
        msg += f"• *Total Pacientes:* {total_pacientes}\n"
        msg += f"• *Urgencias ($\\ge 3$d):* {len(urg_criticos)}\n"
        msg += f"• *Hospitalización ($\\ge 8$d):* {len(hosp_criticos)}\n"
        msg += f"• *UCI ($\\ge 8$d):* {len(uci_criticos)}\n"

        await update.message.reply_text(msg, parse_mode='Markdown')

        # 2. Detalle Urgencias >= 3 días
        if len(urg_criticos) > 0:
            msg_u = "🚨 *URGENCIAS $\\ge 3$ DÍAS:*\n"
            for _, r in urg_criticos.iterrows():
                msg_u += f"• Cama {r.get(col_cama,'-')} - {str(r.get(col_paciente,''))[:22]} ({int(r.get('DIAS_NUM',0))}d)\n"
            await update.message.reply_text(msg_u, parse_mode='Markdown')

        # 3. Detalle Hospitalización >= 8 días
        if len(hosp_criticos) > 0:
            msg_h = "🚨 *HOSPITALIZACIÓN $\\ge 8$ DÍAS:*\n"
            for _, r in hosp_criticos.iterrows():
                msg_h += f"• Cama {r.get(col_cama,'-')} - {str(r.get(col_paciente,''))[:22]} ({int(r.get('DIAS_NUM',0))}d)\n"
            await update.message.reply_text(msg_h, parse_mode='Markdown')

        # 4. Detalle UCI >= 8 días
        if len(uci_criticos) > 0:
            msg_uc = "🚨 *UCI $\\ge 8$ DÍAS:*\n"
            for _, r in uci_criticos.iterrows():
                msg_uc += f"• Cama {r.get(col_cama,'-')} - {str(r.get(col_paciente,''))[:22]} ({int(r.get('DIAS_NUM',0))}d)\n"
            await update.message.reply_text(msg_uc, parse_mode='Markdown')

        # 5. Especialidades (Conteo real agrupado)
        if col_esp:
            conteo_esp = df[col_esp].dropna().astype(str).str.strip().value_counts().head(4)
            msg_es = "🩺 *TOP 4 ESPECIALIDADES:*\n"
            for esp, cant in conteo_esp.items():
                msg_es += f"• {esp.upper()}: {cant} pacientes\n"
            await update.message.reply_text(msg_es, parse_mode='Markdown')
        else:
            await update.message.reply_text("🩺 Columna de especialidad no identificada.", parse_mode='Markdown')

        # 6. Diagnósticos en UCI
        if len(uci) > 0 and col_dx:
            top_dx = df.loc[uci.index, col_dx].dropna().astype(str).str.strip().value_counts().head(3)
            msg_d = "🧠 *TOP 3 DIAGNÓSTICOS UCI:*\n"
            for dx, cnt in top_dx.items():
                msg_d += f"• {dx[:35]} ({cnt})\n"
            await update.message.reply_text(msg_d, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)[:150]}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.Document.ALL, procesar_censo))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
