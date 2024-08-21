from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.mime.text import MIMEText
import time
from datetime import datetime

# Importación necesaria para el estilo del DataFrame
import jinja2

def fetch_and_process_data():
    # Configurar opciones de Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Ejecutar en modo headless, sin abrir la ventana del navegador

    driver = None
    
    try:
        # Inicializar el ChromeDriver con el ejecutable que ya tienes instalado
        driver = webdriver.Chrome(options=chrome_options)

        # URL de la página web
        url = 'https://www.bolsasymercados.es/bme-exchange/es/Mercados-y-Cotizaciones/Acciones/Mercado-Continuo/Precios/mercado-continuo'

        # Cargar la página web
        driver.get(url)
        time.sleep(5)  # Esperar a que la página se cargue completamente

        # Aceptar cookies si el botón está presente
        try:
            accept_cookies_button = driver.find_element(By.ID, 'onetrust-accept-btn-handler')
            accept_cookies_button.click()
            time.sleep(2)  # Esperar a que la acción de aceptar cookies se complete
        except Exception as e:
            print(f"No se encontró el botón de aceptar cookies: {e}")

        # Hacer clic en el botón "Ver todas" para cargar todos los datos
        try:
            ver_todas_button = driver.find_element(By.XPATH, '//a[text()="Ver todas"]')
            ver_todas_button.click()
            time.sleep(5)  # Esperar a que los datos se carguen completamente
        except Exception as e:
            print(f"No se pudo hacer clic en el botón 'Ver todas': {e}")

        # Encontrar la tabla
        table = driver.find_element(By.CLASS_NAME, 'table-responsive')
        rows = table.find_elements(By.TAG_NAME, 'tr')[1:]

        data = []
        omitted_rows = []
        for row in rows:
            # Verificar si la fila contiene alguna celda con colspan="2" y "Suspendido"
            if any(cell.get_attribute('colspan') == '2' and "Suspendido" in cell.text for cell in row.find_elements(By.TAG_NAME, 'td')):
                company_name = row.find_elements(By.TAG_NAME, 'td')[0].text
                suspended_info = row.find_elements(By.TAG_NAME, 'td')[-1].text
                omitted_rows.append(f"{company_name}: {suspended_info}")
                continue  # Si encuentra una celda con colspan="2" y "Suspendido", saltar la fila

            cols = row.find_elements(By.TAG_NAME, 'td')
            cols = [ele.text.strip() for ele in cols]
            data.append(cols)

        headers = [header.text for header in table.find_elements(By.TAG_NAME, 'th')]
        df = pd.DataFrame(data, columns=headers)
        
        # Eliminar las columnas 'Fecha' y 'Hora'
        if 'Fecha' in df.columns and 'Hora' in df.columns:
            df = df.drop(columns=['Fecha', 'Hora'])

        # Convertir columnas numéricas
        df['Último'] = df['Último'].apply(convert_to_float)
        df['Máximo'] = df['Máximo'].apply(convert_to_float)
        df['Mínimo'] = df['Mínimo'].apply(convert_to_float)

        # Convertir la columna '% Dif.' a float después de eliminar el símbolo '%' y cambiar la coma por punto
        df['% Dif.'] = df['% Dif.'].str.replace(',', '.').str.replace('%', '').astype(float)

        # Convertir de vuelta a string y cambiar el punto por coma para presentación
        df['% Dif.'] = df['% Dif.'].apply(lambda x: f"{x:.2f}".replace('.', ',') if pd.notnull(x) else '-')
        
        # Aplicar formato de color a la columna '% Dif.'
        df_styled = df.style.applymap(color_green_red_with_symbol, subset=['% Dif.'])

        # Formatear las columnas "Volumen" y "Efectivo (miles €)"
        for col in ["Volumen", "Efectivo (miles €)"]:
            df[col] = pd.to_numeric(df[col].str.replace('.', '').str.replace(',', '.'), errors='coerce')
            df[col] = df[col].apply(lambda x: '{:,.2f}'.format(x).rstrip('0').rstrip('.') if pd.notnull(x) else '-')
            df[col] = df[col].str.replace('.', ',')

        # Formatear las columnas "Último", "Máximo" y "Mínimo" como moneda, usando coma como separador decimal
        for col in ["Último", "Máximo", "Mínimo"]:
            df[col] = df[col].apply(lambda x: '{:,.4f}'.format(x).replace('.', ',').rstrip('0').rstrip(',') if pd.notnull(x) else '-')

        # Obtener la fecha de hoy
        today = datetime.today().strftime('%d-%m-%Y')

        # Crear un archivo Excel sin las cabeceras
        file_name = f'{today}_mercado_continuo.xlsx'
        df_styled.to_excel(file_name, index=False, header=False)

        return file_name, omitted_rows, today

    except Exception as e:
        print(f"Error durante la ejecución: {e}")
        return None, None, None
    
    finally:
        if driver:
            driver.quit()

def convert_to_float(value):
    """Función para convertir una cadena con coma decimal a un número float."""
    try:
        # Reemplazar coma por punto para la conversión
        return float(value.replace(',', '.'))
    except (ValueError, AttributeError):
        # Devolver NaN si no se puede convertir a float
        return float('nan')

def color_green_red_with_symbol(val):
    color = 'black'
    if isinstance(val, str) and '%' in val:
        val_num = float(val.replace('%', ''))
        if val_num > 0:
            color = 'green'
        elif val_num < 0:
            color = 'red'
    return f'color: {color};'

def send_email(file_name, omitted_rows, today):
    from_address = 'jczaragozatomas@gmail.com'
    to_address = 'laura.deluis@diariodelaltoaragon.es'
    subject = f'Datos del Mercado Continuo - {today}'
    body = 'Adjunto encontrarás los datos del Mercado Continuo.\n\nLas siguientes filas no se incluyeron por estar suspendidas:\n\n'

    if omitted_rows:
        body += '\n'.join(omitted_rows)
    else:
        body += 'No se encontraron empresas suspendidas.'

    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = to_address
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    with open(file_name, 'rb') as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename= {file_name}")

    msg.attach(part)

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(from_address, 'fyzb avcl thot jkxl')
    text = msg.as_string()
    server.sendmail(from_address, to_address, text)
    server.quit()

def job():
    file_name, omitted_rows, today = fetch_and_process_data()
    if file_name:
        send_email(file_name, omitted_rows, today)
    else:
        print("No se pudo procesar la tabla y enviar el correo.")

# Ejecutar el trabajo inmediatamente
job()

















