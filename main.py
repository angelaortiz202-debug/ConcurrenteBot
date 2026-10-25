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
        "¡Hola Angela! Envíame el archivo `.xlsx` del censo diario para procesar las alertas instantáneamente.",
        parse_mode='Markdown'
    )

async def procesar_censo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    documento = update.message.document
    if not documento or not documento.file_name.endswith(('.xlsx', '.xls')):
        await update.message.reply_text("❌ Por favor envía un archivo de Excel válido (.xlsx).")
        return

    await update.message.reply_text("⏳ Procesando censo hospitalario completo...")

    try:
        file = await context.bot.get_file(documento.file_id)
        file_bytes = await file.download_as_bytearray()
        
        # Lee todo el censo (todas las filas y columnas)
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)
        
        # Limpiar espacios en los nombres de las columnas del Excel
        df.columns = df.columns.str.strip().str.upper()

        total_pacientes = len(df)
        
        # Detección inteligente de columnas clave
        col_aut = next((c for c in df.columns if 'AUTORIZAC' in c), 'NUMERO AUTORIZACIÓN')
        col_dias = next((c for c in df.columns if 'DIAS' in c or 'ESTANCIA' in c), 'DIAS TRANSCURRIDOS')
        col_cama = next((c for c in df.columns if 'CAMA' in c), df.columns[0])
        col_paciente = next((c for c in df.columns if 'PACIENTE' in c or 'NOMBRE' in c), df.columns[1])
        col_eps = next((c for c in df.columns if 'ENTIDAD' in c or 'EPS' in c), df.columns[2])
        col_valor = next((c for c in df.columns if 'VALOR' in c or 'COSTO' in c), None)

        def clasificar(row):
            val_aut = row.get(col_aut, None)
            sin_aut = pd.isna(val_aut) or str(val_aut).strip() == '' or str(val_aut).strip() == '0'
            try:
                dias = float(str(row.get(col_dias, 0)).replace(',', '.'))
            except:
                dias = 0
                
            if sin_aut or dias >= 5:
                return 'CRITICO'
            return 'OK'

        df['ALERTA'] = df.apply(clasificar, axis=1)
        criticos = df[df['ALERTA'] == 'CRITICO']
        
        num_criticos = len(criticos)
        monto_total = df[col_valor].sum() if col_valor and col_valor in df.columns else 0

        # 1. Resumen Ejecutivo Global del Censo Masivo
        msg = f"📊 *INFORME DE AUDITORÍA CONCURRENTE*\n"
        msg += f"🏥 *DIAGNOSTICO ADAX*\n\n"
        msg += f"• *Total Pacientes en Censo:* {total_pacientes}\n"
        msg += f"• *Casos Críticos (Estancia $\\ge$ 5d o Sin Aut):* {num_criticos}\n"
        if monto_total > 0:
            msg += f"• *Monto Financiero Consolidado:* ${monto_total:,.0f}\n"

        await update.message.reply_text(msg, parse_mode='Markdown')

        # 2. Detalle de los casos críticos más relevantes
        if num_criticos > 0:
            msg_det = f"🔴 *TOP 10 CASOS CRÍTICOS (de {num_criticos} totales):*\n"
            for idx, row in criticos.head(10).iterrows():
                cama = row.get(col_cama, 'S/C')
                paciente = str(row.get(col_paciente, 'SIN NOMBRE'))[:25]
                dias = row.get(col_dias, 0)
                eps = str(row.get(col_eps, 'N/A'))[:15]
                aut_val = row.get(col_aut, 'Sin Aut')
                aut_txt = "⚠️ SIN AUTORIZACIÓN" if pd.isna(aut_val) or str(aut_val).strip() == '' else f"Aut: {aut_val}"
                
                msg_det += f"\n• *Cama {cama}* - {paciente}\n"
                msg_det += f"  Estancia: {dias} días | {aut_txt}\n"
                msg_det += f"  EPS: {eps}\n"

            if num_criticos > 10:
                msg_det += f"\n_...y {num_criticos - 10} casos críticos adicionales procesados._"

            await update.message.reply_text(msg_det, parse_mode='Markdown')
        else:
            await update.message.reply_text("✅ ¡Excelente! No se registran pacientes críticos bajo los criterios evaluados en todo el censo.", parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error procesando la estructura masiva del Excel: {str(e)[:150]}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.Document.ALL, procesar_censo))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
