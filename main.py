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
        "¡Hola Angela! Envíame tu censo en `.xlsx` para generar el informe clínico exacto.",
        parse_mode='Markdown'
    )

async def procesar_censo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    documento = update.message.document
    if not documento or not documento.file_name.endswith(('.xlsx', '.xls')):
        await update.message.reply_text("❌ Por favor envía un archivo de Excel válido (.xlsx).")
        return

    await update.message.reply_text("⏳ Analizando censo con nombres de columnas exactos...")

    try:
        file = await context.bot.get_file(documento.file_id)
        file_bytes = await file.download_as_bytearray()
        
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)
        df.columns = df.columns.str.strip().str.upper()

        total_pacientes = len(df)
        
        # --- BÚSQUEDA EXACTA DE COLUMNAS CLAVE ---
        col_servicio = next((c for c in df.columns if 'SERVICIO' in c or 'UBICACION' in c or 'AREA' in c), None)
        col_esp = next((c for c in df.columns if 'ESPECIALIDAD' in c or 'MEDICO' in c or 'TRATANTE' in c), None)
        col_dx = next((c for c in df.columns if 'DIAGNOSTICO' in c or 'DX' in c or 'PATOLOGIA' in c), None)
        
        # Buscar columna de días o estancia de forma precisa
        col_dias = next((c for c in df.columns if 'DIAS' in c or 'ESTANCIA' in c or 'TRANS' in c), None)
        if not col_dias:
            col_dias = df.columns[3] # fallback predeterminado si no lo halla

        col_cama = next((c for c in df.columns if 'CAMA' in c), df.columns[0])
        col_paciente = next((c for c in df.columns if 'PACIENTE' in c or 'NOMBRE' in c), df.columns[1])
        col_eps = next((c for c in df.columns if 'ENTIDAD' in c or 'EPS' in c), df.columns[2])

        # Normalizar textos para filtros seguros
        df['SRV_LOWER'] = df[col_servicio].astype(str).str.lower() if col_servicio else ''
        df['ESP_LOWER'] = df[col_esp].astype(str).str.lower() if col_esp else ''
        df['DX_LOWER'] = df[col_dx].astype(str).str.lower() if col_dx else ''

        # Forzar columna de días a numérica
        df[col_dias] = pd.to_numeric(df[col_dias], errors='coerce').fillna(0)

        # --- FILTROS POR SERVICIO Y ESTANCIA ---
        urgencias = df[df['SRV_LOWER'].str.contains('urgenc', na=False)]
        hosp = df[df['SRV_LOWER'].str.contains('hospit', na=False)]
        uci = df[df['SRV_LOWER'].str.contains('uci|unidad de cuidado', na=False)]

        urg_criticos = urgencias[urgencias[col_dias] >= 3]
        hosp_criticos = hosp[hosp[col_dias] >= 8]
        uci_criticos = uci[uci[col_dias] >= 8]

        # 1. Resumen Global
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

        # 5. Consolidado por Especialidades (Leyendo la columna exacta)
        msg_esp = "🩺 *CONSOLIDADO POR ESPECIALIDADES:*\n"
        if col_esp:
            # Agrupar directamente de la columna de especialidad del Excel para mostrar los totales reales
            conteo_esp = df[col_esp].dropna().astype(str).str.strip().value_counts().head(5)
            for esp_nombre, cantidad in conteo_esp.items():
                msg_esp += f"\n• *{esp_nombre.upper()}:* {cantidad} pacientes"
        else:
            msg_esp += "\n⚠️ No se detectó la columna 'ESPECIALIDAD'."

        await update.message.reply_text(msg_esp, parse_mode='Markdown')

        # 6. Principales Diagnósticos en UCI
        if len(uci) > 0 and col_dx:
            top_dx = df.loc[uci.index, col_dx].dropna().astype(str).str.strip().value_counts().head(3)
            msg_dx = "🧠 *TOP 3 DIAGNOSTICOS EN UCI:*\n"
            for dx, cuenta in top_dx.items():
                msg_dx += f"• {dx[:40]} ({cuenta} pacientes)\n"
            await update.message.reply_text(msg_dx, parse_mode='Markdown')
        elif len(uci) > 0:
            await update.message.reply_text("🧠 *UCI:* Hay pacientes en UCI pero no se encontró la columna de diagnóstico.", parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error procesando columnas del censo: {str(e)[:150]}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.Document.ALL, procesar_censo))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
