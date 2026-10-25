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
        "¡Hola Angela! Envíame tu censo en `.xlsx` para generar el informe directivo por servicios y especialidades.",
        parse_mode='Markdown'
    )

async def procesar_censo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    documento = update.message.document
    if not documento or not documento.file_name.endswith(('.xlsx', '.xls')):
        await update.message.reply_text("❌ Por favor envía un archivo de Excel válido (.xlsx).")
        return

    await update.message.reply_text("⏳ Analizando estancias, servicios y especialidades...")

    try:
        file = await context.bot.get_file(documento.file_id)
        file_bytes = await file.download_as_bytearray()
        
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)
        df.columns = df.columns.str.strip().str.upper()

        total_pacientes = len(df)
        
        # Detección inteligente de columnas
        col_servicio = next((c for c in df.columns if 'SERVICIO' in c or 'UBICACION' in c or 'AREA' in c), None)
        col_esp = next((c for c in df.columns if 'ESPECIALIDAD' in c or 'MEDICO' in c or 'TRATANTE' in c), None)
        col_aut = next((c for c in df.columns if 'AUTORIZAC' in c), 'NUMERO AUTORIZACIÓN')
        col_dias = next((c for c in df.columns if 'DIAS' in c or 'ESTANCIA' in c), 'DIAS TRANSCURRIDOS')
        col_cama = next((c for c in df.columns if 'CAMA' in c), df.columns[0])
        col_paciente = next((c for c in df.columns if 'PACIENTE' in c or 'NOMBRE' in c), df.columns[1])
        col_eps = next((c for c in df.columns if 'ENTIDAD' in c or 'EPS' in c), df.columns[2])
        col_valor = next((c for c in df.columns if 'VALOR' in c or 'COSTO' in c), None)

        # Normalizar textos para filtros seguros
        if col_servicio:
            df['SRV_LOWER'] = df[col_servicio].astype(str).str.lower()
        else:
            df['SRV_LOWER'] = ''
            
        if col_esp:
            df['ESP_LOWER'] = df[col_esp].astype(str).str.lower()
        else:
            df['ESP_LOWER'] = ''

        # --- 1. BLOQUE URGENCIAS >= 3 DÍAS ---
        urgencias = df[df['SRV_LOWER'].str.contains('urgenc', na=False)]
        urg_criticos = urgencias[urgencias[col_dias] >= 3]

        # --- 2. BLOQUE HOSPITALIZACIÓN >= 8 DÍAS ---
        hosp = df[df['SRV_LOWER'].str.contains('hospit', na=False)]
        hosp_criticos = hosp[hosp[col_dias] >= 8]

        # --- 3. BLOQUE UCI >= 8 DÍAS ---
        uci = df[df['SRV_LOWER'].str.contains('uci|unidad de cuidado', na=False)]
        uci_criticos = uci[uci[col_dias] >= 8]

        monto_total = df[col_valor].sum() if col_valor and col_valor in df.columns else 0

        # --- CONSTRUCCIÓN DEL REPORTE EJECUTIVO ---
        msg = f"📊 *TABLERO DE AUDITORÍA CONCURRENTE*\n"
        msg += f"🏥 *DIAGNOSTICO ADAX*\n\n"
        msg += f"• *Total Censo:* {total_pacientes} pacientes\n"
        if monto_total > 0:
            msg += f"• *Monto Financiero Total:* ${monto_total:,.0f}\n\n"

        # Alertas por Servicio
        msg += f"🚨 *ALERTAS POR TIEMPO DE ESTANCIA:*\n"
        msg += f"• **Urgencias ($\\ge 3$ días):** {len(urg_criticos)} casos\n"
        msg += f"• **Hospitalización ($\\ge 8$ días):** {len(hosp_criticos)} casos\n"
        msg += f"• **UCI ($\\ge 8$ días):** {len(uci_criticos)} casos\n\n"

        await update.message.reply_text(msg, parse_mode='Markdown')

        # --- DETALLE DE URGENCIAS CRÍTICAS (>= 3 días) ---
        if len(urg_criticos) > 0:
            msg_urg = "⚠️ *URGENCIAS CON ESTANCIA $\\ge 3$ DÍAS:*\n"
            for _, r in urg_criticos.head(5).iterrows():
                msg_urg += f"• Cama {r.get(col_cama,'-')} - {str(r.get(col_paciente,''))[:22]} | Estancia: {r.get(col_dias,0)}d | {r.get(col_eps,'')[:12]}\n"
            await update.message.reply_text(msg_urg, parse_mode='Markdown')

        # --- DETALLE DE HOSPITALIZACIÓN CRÍTICA (>= 8 días) ---
        if len(hosp_criticos) > 0:
            msg_hosp = "⚠️ *HOSPITALIZACIÓN CON ESTANCIA $\\ge 8$ DÍAS:*\n"
            for _, r in hosp_criticos.head(5).iterrows():
                msg_hosp += f"• Cama {r.get(col_cama,'-')} - {str(r.get(col_paciente,''))[:22]} | Estancia: {r.get(col_dias,0)}d | {r.get(col_eps,'')[:12]}\n"
            await update.message.reply_text(msg_hosp, parse_mode='Markdown')

        # --- 4. DESGLOSE POR ESPECIALIDADES CLAVE ---
        msg_esp = "🩺 *CONSOLIDADO POR ESPECIALIDADES:*\n"
        especialidades_objetivo = [
            ('Medicina Interna', 'interna|medicina interna'),
            ('Ortopedia', 'ortoped'),
            ('Urología', 'urolog'),
            ('Cirugía General', 'cirugia general|cirugía'),
            ('Medicina General', 'medicina general|general')
        ]

        for nombre_esp, patron in especialidades_objetivo:
            subset = df[df['ESP_LOWER'].str.contains(patron, na=False)]
            cantidad = len(subset)
            msg_esp.f += f"\n• *{nombre_esp}:* {cantidad} pacientes"
            if cantidad > 0:
                # Mostrar breve detalle de los primeros de esta especialidad
                nombres_resumen = ", ".join([str(x)[:15] for x in subset[col_paciente].head(3).values])
                msg_esp += f" _(Ej: {nombres_resumen})_"

        await update.message.reply_text(msg_esp, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error procesando indicadores especializados: {str(e)[:150]}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.Document.ALL, procesar_censo))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
