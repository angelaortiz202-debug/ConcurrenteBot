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

    await update.message.reply_text("⏳ Analizando el censo hospitalario...")

    try:
        file = await context.bot.get_file(documento.file_id)
        file_bytes = await file.download_as_bytearray()
        
        # Lee la primera hoja automáticamente
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)
        
        def clasificar(row):
            sin_aut = pd.isna(row['NUMERO AUTORIZACIÓN']) or str(row['NUMERO AUTORIZACIÓN']).strip() == ''
            dias = row['DIAS TRANSCURRIDOS']
            if sin_aut or dias >= 5:
                return 'CRITICO'
            return 'OK'

        df['ALERTA'] = df.apply(clasificar, axis=1)
        criticos = df[df['ALERTA'] == 'CRITICO']
        
        total = len(df)
        num_criticos = len(criticos)
        valor_total = df['VALOR'].sum() if 'VALOR' in df.columns else 0
        
        msg = f"📊 *RESUMEN DE AUDITORÍA DIARIA*\n\n"
        msg += f"• *Total Censo:* {total} pacientes\n"
        msg += f"• *Casos Críticos (🔴):* {num_criticos}\n"
        if valor_total > 0:
            msg += f"• *Monto Expuesto:* ${valor_total:,.0f}\n"
        msg += f"\n🔴 *TOP PACIENTES CRÍTICOS:* (Mostrando primeros 10)\n"
        
        # Limitamos a 10 para que nunca exceda el tamaño permitido por Telegram
        for idx, row in criticos.head(10).iterrows():
            aut = "⚠️ SIN AUTORIZACIÓN" if pd.isna(row['NUMERO AUTORIZACIÓN']) else row['NUMERO AUTORIZACIÓN']
            msg += f"\n• *Cama {row.get('CAMA', 'N/A')}* - {row.get('NOMBRE DEL PACIENTE', 'N/A')}\n"
            msg += f"  Estancia: {row.get('DIAS TRANSCURRIDOS', 0)} días | Aut: {aut}\n"
            msg += f"  EPS: {row.get('ENTIDAD', 'N/A')}\n"

        if len(criticos) > 10:
            msg += f"\n_...y {len(criticos) - 10} casos críticos adicionales._"

        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"⚠️ Ocurrió un error al procesar la hoja de Excel: {str(e)}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.Document.ALL, procesar_censo))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
