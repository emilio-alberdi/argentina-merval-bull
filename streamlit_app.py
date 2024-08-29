import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt

# Configuración de la página
st.set_page_config(page_title="Bull Spread Analyzer", layout="wide")

# Título de la aplicación
st.title("Bull Spread Analyzer")

# Parámetros de entrada configurables por el usuario
lotes = st.number_input("Número de Lotes", value=10, min_value=1)
percentageDifference = st.number_input("Diferencia de Porcentaje Máxima (%)", value=30, min_value=0, max_value=100)
highRange = st.number_input("Multiplicador de Rango Superior (%)", value=1.05, min_value=1.0, max_value=2.0, step=0.01)

# Funciones auxiliares
def extract_option_type(option_code):
    return option_code[3]

def convert_spanish_format_to_float(df, columns):
    for column in columns:
        df[column] = df[column].astype(str)
        df[column] = df[column].str.replace('.', '', regex=False)
        df[column] = df[column].str.replace(',', '.', regex=False)
        df[column] = pd.to_numeric(df[column], errors='coerce')
    return df

def extract_strike_price(option_code):
    base_str = option_code[4:-2]
    if option_code[-2].isdigit():
        base_str = option_code[4:-1]
        return float(base_str) / 10
    return float(base_str)

def extract_expiration(option_code):
    if not option_code[-2].isdigit():
        expiration_code = option_code[-2:]
        expiration_map_two_chars = {
            'OC': 'Octubre',
            'NO': 'Noviembre',
            'DI': 'Diciembre',
            'EN': 'Enero',
            'FE': 'Febrero',
            'MR': 'Marzo',
            'AB': 'Abril',
            'MY': 'Mayo',
            'JN': 'Junio',
            'JL': 'Julio',
            'AG': 'Agosto',
            'SE': 'Septiembre'
        }
        return expiration_map_two_chars.get(expiration_code, 'Desconocido')
    else:
        expiration_code = option_code[-1]
        expiration_map_one_char = {
            'F': 'Febrero',
            'A': 'Abril',
            'J': 'Junio',
            'G': 'Agosto',
            'O': 'Octubre',
            'D': 'Diciembre'
        }
        return expiration_map_one_char.get(expiration_code, 'Desconocido')

# URL de la página a scrappear
url = "https://bolsar.info/opciones.php"

# Solicitar los datos
response = requests.get(url)
response.raise_for_status()
soup = BeautifulSoup(response.text, 'html.parser')

# Extraer la tabla
table = soup.find('table', {'class': 'tabla_cierre'})
rows = table.find_all('tr')

# Convertir los datos a un DataFrame de pandas
data = []
for row in rows[1:]:
    cells = row.find_all('td')
    data.append([cell.get_text(strip=True) for cell in cells])

columns = ['Activo Subyacente', 'Especie', 'Cant. Nominal', 'Compra', 'Venta', 'Cant. Nominal', 'Último', 'Variación', 'Apertura', 'Máx', 'Mín', 'Cierre Ant.', 'Vol. Nominal', 'Monto', 'Cant. Ope.', 'Hora']
df = pd.DataFrame(data, columns=columns)

# Convertir columnas numéricas de formato español a float
df = convert_spanish_format_to_float(df, ['Último', 'Variación', 'Apertura', 'Máx', 'Mín', 'Cierre Ant.', 'Vol. Nominal', 'Monto'])

# Agregar columnas adicionales
df['Strike Price'] = df['Especie'].apply(extract_strike_price)
df['Option Type'] = df['Especie'].apply(extract_option_type)
df['Expiration'] = df['Especie'].apply(extract_expiration)

# Obtener precios actuales de los activos subyacentes
unique_assets = df['Activo Subyacente'].unique()
prices = {}
for asset in unique_assets:
    ticker = yf.Ticker(asset + '.BA')
    current_price = ticker.history(period='1d')['Close'].iloc[-1]
    prices[asset] = current_price

df['Precio Actual'] = df['Activo Subyacente'].map(prices)
df['5% Superior'] = df['Precio Actual'] * highRange

# Agrupar y crear pares
grouped = df[(df['Option Type'] == 'C')].groupby(['Activo Subyacente', 'Option Type', 'Expiration'])
group_pairs = []
for name, group in grouped:
    group = group.sort_values(by='Strike Price')
    group['Strike Price Difference'] = group['Strike Price'].diff()
    group['Especie Anterior'] = group['Especie'].shift(1)
    group['Último Anterior'] = group['Último'].shift(1)
    group['Percentage Difference'] = np.where(
        group['Strike Price Difference'] != 0, 
        (group['Último'] / group['Strike Price Difference']) * 100, 
        np.nan
    )
    pairs = [(row1, row2) for (index1, row1), (index2, row2) in zip(group.iterrows(), group.shift(-1).iterrows()) if not pd.isnull(row2['Especie'])]
    group_pairs.extend(pairs)

# Filtrar pares válidos
valid_pairs = []
for row1, row2 in group_pairs:
    if (row1['Strike Price'] <= row1['5% Superior'] and row2['Percentage Difference'] <= percentageDifference):
        valid_pairs.append((row1, row2))

# Mostrar resultados
if valid_pairs:
    for idx, (row1, row2) in enumerate(valid_pairs):
        strike1 = row1['Strike Price']
        strike2 = row2['Strike Price']
        price1 = row1['Último']
        price2 = row2['Último']
        
        precios_subyacentes = np.linspace(strike1 * 0.8, strike2 * 1.2, 100)
        ganancia = np.where(precios_subyacentes < strike1, 0,
                            np.where(precios_subyacentes > strike2, strike2 - strike1,
                                     precios_subyacentes - strike1)) - (price1 - price2)
        ganancia_total = ganancia * lotes * 100

        # Graficar el Bull Spread
        st.subheader(f'{row1["Activo Subyacente"]} - Vencimiento: {row1["Expiration"]}')
        plt.figure(figsize=(8, 4))
        plt.plot(precios_subyacentes, ganancia_total, label=f'Bull Spread {strike1} - {strike2}')
        plt.axhline(0, color='black', linestyle='--')
        plt.title(f'Bull Spread #{idx + 1}: {strike1} - {strike2}')
        plt.ylabel('Ganancia/Pérdida Total')
        plt.legend()
        plt.grid(True)
        st.pyplot(plt)
else:
    st.write("No se encontraron pares válidos para el Bull Spread.")
