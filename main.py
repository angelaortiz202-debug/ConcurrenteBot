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
        "¡Hola Angela! Envíame tu censo en `.xlsx` para generar el informe de estancias y especialidades.",
        parse_mode='Markdown'
    )

async def procesar_censo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    documento = update.message.document
    if not documento or not documento.file_name.endswith(('.xlsx', '.xls')):
        await update.message.reply_text("❌ Por favor envía un archivo de Excel válido (.xlsx).")
        return

    await update.message.reply_text("⏳ Procesando estancias y especialidades clínicas...")

    try:
        file = await context.bot.get_file(documento.file_id)
        file_bytes = await file.download_as_bytearray()
        
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)
        df.columns = df.columns.str.strip().str.upper()

        total_pacientes = len(df)
        
        # Detección inteligente de columnas
        col_servicio = next((c for c in df.columns if 'SERVICIO' in c or 'UBICACION' in c or 'AREA' in c), None)
        col_esp = next((c for c in df.columns if 'ESPECIALIDAD' in c or 'MEDICO' in c or 'TRATANTE' in c), None)
        col_dx = next((c for c in df.columns if 'DIAGNOSTICO' in c or 'DX' in c or 'PATOLOGIA' in c), None)
        col_dias = next((c for c in df.columns if 'DIAS' in c or 'ESTANCIA' in c), 'DIAS TRANSCURRIDOS')
        col_cama = next((c for c in df.columns if 'CAMA' in c), df.columns[0])
        col_paciente = next((c for c in df.columns if 'PACIENTE' in c or 'NOMBRE' in c), df.columns[1])
        col_eps = next((c for c in df.columns if 'ENTIDAD' in c or 'EPS' in c), df.columns[2])

        # Normalizar textos para filtros seguros
        df['SRV_LOWER'] = df[col_servicio].astype(str).str.lower() if col_servicio else ''
        df['ESP_LOWER'] = df[col_esp].astype(str).str.lower() if col_esp else ''
        df['DX_LOWER'] = df[col_dx].astype(str).str.lower() if col_dx else ''

        # Asegurar que días sea numérico
        df[col_dias] = pd.to_numeric(df[col_dias], errors='coerce').fillna(0)

        # --- SEPARACIÓN POR SERVICIOS ---
        urgencias = df[df['SRV_LOWER'].str.contains('urgenc', na=False)]
        hosp = df[df['SRV_LOWER'].str.contains('hospit', na=False)]
        uci = df[df['SRV_LOWER'].str.contains('uci|unidad de cuidado', na=False)]

        # --- UMBRALES CRÍTICOS DE ESTANCIA ---
        urg_criticos = urgencias[urgencias[col_dias] >= 3]
        hosp_criticos = hosp[hosp[col_dias] >= 8]
        uci_criticos = uci[uci[col_dias] >= 8]

        # 1. Resumen Global de Alertas
        msg = f"📊 *INFORME EJECUTIVO DE CONCURRENCIA*\n"
        msg += f"🏥 *DIAGNOSTICO ADAX*\n\n"
        msg += f"• *Total Pacientes en Censo:* {total_pacientes}\n\n"
        
        msg += f"🚨 *ALERTAS DE ESTANCIA PROLONGADA:*\n"
        msg += f"• Urgencias ($\\ge 3$ días): *{len(urg_criticos)}* casos\n"
        msg += f"• Hospitalización ($\\ge 8$ días): *{len(hosp_criticos)}* casos\n"
        msg += f"• UCI ($\\ge 8$ días): *{len(uci_criticos)}* casos\n"

        await update.message.reply_text(msg, parse_mode='Markdown')

        # 2. Detalle Urgencias >= 3 días
        if len(urg_criticos) > 0:
            msg_urg = "🚨 *URGENCIAS $\\ge 3$ DÍAS (Detalle):*\n"
            for _, r in urg_criticos.iterrows():
                msg_urg += f"• Cama {r.get(col_cama,'-')} - {str(r.get(col_paciente,''))[:25]}\n"
                msg_urg += f"  Estancia: *{int(r.get(col_dias,0))} días* | EPS: {str(r.get(col_eps,''))[:20]}\n"
            await update.message.reply_text(msg_urg, parse_mode='Markdown')

        # 3. Detalle Hospitalización >= 8 días
        if len(hosp_criticos) > 0:
            msg_hosp = "🚨 *HOSPITALIZACIÓN $\\ge 8$ DÍAS (Detalle):*\n"
            for _, r in hosp_criticos.iterrows():
                msg_hosp += f"• Cama {r.get(col_cama,'-')} - {str(r.get(col_paciente,''))[:25]}\n"
                msg_hosp += f"  Estancia: *{int(r.get(col_dias,0))} días* | EPS: {str(r.get(col_eps,''))[:20]}\n"
            await update.message.reply_text(msg_hosp, parse_mode='Markdown')

        # 4. Detalle UCI >= 8 días
        if len(uci_criticos) > 0:
            msg_uci = "🚨 *UCI $\\ge 8$ DÍAS (Detalle):*\n"
            for _, r in uci_criticos.iterrows():
                msg_uci += f"• Cama {r.get(col_cama,'-')} - {str(r.get(col_paciente,''))[:25]}\n"
                msg_uci += f"  Estancia: *{int(r.get(col_dias,0))} días* | EPS: {str(r.get(col_eps,''))[:20]}\n"
            await update.message.reply_text(msg_uci, parse_mode='Markdown')

        # 5. Top Especialidades (Urgencias y Hospitalización)
        msg_esp = "🩺 *CONSOLIDADO POR ESPECIALIDADES:*\n"
        lista_esp = [
            ('Medicina Interna', 'interna'),
            ('Ortopedia', 'ortoped'),
            ('Urología', 'urolog'),
            ('Cirugía General', 'cirugi')
        ]

        for nombre_esp, patron in lista_esp:
            subset = df[df['ESP_LOWER'].str.contains(patron, na=False)]
            cant = len(subset)
            msg_esp += f"\n• *{nombre_esp}:* {cant} pacientes"
            if cant > 0:
                nombres = ", ".join([str(x)[:15] for x in subset[col_paciente].head(2).values])
                msg_esp += f" (Ej: {nombres})"

        await update.message.reply_text(msg_esp, parse_mode='Markdown')

        # 6. Principales Diagnósticos en UCI
        if len(uci) > 0 and col_dx:
            top_dx = uci[col_dx].value_counts().head(3)
            msg_dx = "🧠 *TOP 3 DIAGNOSTICOS EN UCI:*\n"
            for dx, cuenta in top_dx.items():
                msg_dx += f"• {str(dx)[:35]} ({cuenta} pacientes)\n"
            await update.message.reply_text(msg_dx, parse_mode='Markdown')
        elif len(uci) > 0:
            await update.message.reply_text("🧠 *UCI:* Hay pacientes en UCI pero no se detectó columna de diagnósticos.", parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error procesando reporte clínico: {str(e)[:150]}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.Document.ALL, procesar_censo))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
