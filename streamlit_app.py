# Author: https://x.com/emilioalberdi 2024
# No warranties. Use it as you like. Happy coding!

import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import yfinance as yf

import pandas as pd
import matplotlib.pyplot as plt

lotes = 10
percentageDifference = 30
highRange = 1.05


def extract_option_type(option_code):
    """
    Extracts the option type (Call or Put) from the 'Especie' column.
    
    :param option_code: The value from the 'Especie' column (e.g., 'PAMC2380OC').
    :return: 'C' for Call and 'V' for Put.
    """
    # The option type is the second to last character
    return option_code[3]

def convert_spanish_format_to_float(df, columns):
    """
    Converts columns with Spanish number format (comma as decimal separator, dot as thousand separator) to floats.
    
    :param df: DataFrame containing the columns to convert.
    :param columns: List of column names to convert.
    :return: DataFrame with converted columns.
    """
    for column in columns:
        # Convert the column to string to ensure compatibility with .str methods
        df[column] = df[column].astype(str)
        # Replace thousand separator (.) with nothing
        df[column] = df[column].str.replace('.', '', regex=False)
        # Replace decimal separator (,) with a dot (.)
        df[column] = df[column].str.replace(',', '.', regex=False)
        # Convert the cleaned column to float
        df[column] = pd.to_numeric(df[column], errors='coerce')
    
    return df

def extract_strike_price(option_code):
    """
    Extrae el precio de ejercicio (Strike Price) de la columna 'Especie'.
    Si el anteúltimo carácter es un número, divide el precio de ejercicio por 10.
    
    :param option_code: El valor de la columna 'Especie' (ej. 'PAMC2380OC').
    :return: El precio de ejercicio como float.
    """
    # Asumimos que el Strike Price empieza desde la 5ª posición hasta los últimos 1 o 2 caracteres que indican el vencimiento
    base_str = option_code[4:-2]
    if option_code[-2].isdigit():  # Si el penúltimo carácter es un dígito
        base_str = option_code[4:-1]
        return float(base_str) / 10
    return float(base_str)

def extract_expiration(option_code):
    """
    Extrae el vencimiento basado en el/los último(s) carácter(es) del código 'Especie'.
    
    :param option_code: El valor de la columna 'Especie' (ej. 'PAMC2380OC').
    :return: Un string que representa el mes de vencimiento.
    """
    if not option_code[-2].isdigit():  # Si el último carácter no es un dígito
        
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
    else:  # Si el último carácter es un dígito, usamos solo el último carácter
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

# Ahora df tiene las columnas especificadas convertidas a formato float


# Ajustar las opciones de Pandas para mostrar todas las columnas
pd.set_option('display.max_columns', None)  # No limitar el número de columnas mostradas
pd.set_option('display.expand_frame_repr', False)  # Evitar que las filas se dividan en varias líneas

# URL de la página a scrappear
url = "https://bolsar.info/opciones.php"

# Realizar la solicitud HTTP a la página
response = requests.get(url)
response.raise_for_status()  # Esto lanzará un error si la solicitud no fue exitosa

# Analizar el contenido HTML de la página
soup = BeautifulSoup(response.text, 'html.parser')

# Encontrar la tabla que contiene los datos
table = soup.find('table', {'class': 'tabla_cierre'})  # Cambia la clase según la estructura HTML de la página

# Extraer los datos de la tabla
rows = table.find_all('tr')

# Crear una lista para almacenar los datos
data = []

# Recorrer cada fila de la tabla y extraer las celdas
for row in rows[1:]:  # Omitir la primera fila (cabecera)
    cells = row.find_all('td')
    data.append([cell.get_text(strip=True) for cell in cells])

# Convertir los datos a un DataFrame de pandas
columns = ['Activo Subyacente', 'Especie', 'Cant. Nominal', 'Compra', 'Venta', 'Cant. Nominal', 'Último', 'Variación', 'Apertura', 'Máx', 'Mín', 'Cierre Ant.', 'Vol. Nominal', 'Monto', 'Cant. Ope.', 'Hora']
df = pd.DataFrame(data, columns=columns)


# Aplicar la función al DataFrame
df = convert_spanish_format_to_float(df, ['Último', 'Variación', 'Apertura', 'Máx', 'Mín', 'Cierre Ant.', 'Vol. Nominal', 'Monto'])

# Add the 'Strike Price' column using the extract_strike_price function
df['Strike Price'] = df['Especie'].apply(extract_strike_price)

# Add the 'Option Type' column using the extract_option_type function
df['Option Type'] = df['Especie'].apply(extract_option_type)

# Aplicar la función para crear la columna 'Expiration'
df['Expiration'] = df['Especie'].apply(extract_expiration)

unique_assets = df['Activo Subyacente'].unique()

# Crear un diccionario para almacenar los precios de las acciones
prices = {}

# Obtener el precio de cada activo subyacente
for asset in unique_assets:
    ticker = yf.Ticker(asset + '.BA')  # .BA es el sufijo para tickers de Argentina en Yahoo Finance
    current_price = ticker.history(period='1d')['Close'].iloc[-1]
    prices[asset] = current_price


# Crear una nueva columna en el DataFrame con los precios actuales de las acciones
df['Precio Actual'] = df['Activo Subyacente'].map(prices)

df['5% Superior'] = df['Precio Actual'] * highRange

grouped = df[(df['Option Type'] == 'C')].groupby(['Activo Subyacente', 'Option Type', 'Expiration'])

# Crear una lista para almacenar todos los pares válidos
group_pairs = []

# Iterar sobre cada grupo para crear pares de filas consecutivas
for name, group in grouped:
    # Ordenar dentro del grupo por 'Strike Price' si no está ya ordenado
    group = group.sort_values(by='Strike Price')

    group['Strike Price Difference'] = group['Strike Price'].diff()

    # Agregar la columna con la 'Especie' anterior
    group['Especie Anterior'] = group['Especie'].shift(1)

    # Agregar la columna con el valor de 'Último' de la especie anterior
    group['Último Anterior'] = group['Último'].shift(1)


    # Calcular el porcentaje entre 'Último' y 'Strike Price Difference'
    group['Percentage Difference'] = np.where(
        group['Strike Price Difference'] != 0, 
        (group['Último'] / group['Strike Price Difference']) * 100, 
        np.nan  # Maneja la división por cero o valores no definidos
    )
    
    # Crear los pares de filas consecutivas
    pairs = [(row1, row2) for (index1, row1), (index2, row2) in zip(group.iterrows(), group.shift(-1).iterrows()) if not pd.isnull(row2['Especie'])]
    
    # Agregar los pares a la lista de pares válidos
    group_pairs.extend(pairs)

# Crear una lista para almacenar las tuplas que cumplen con las condiciones
valid_pairs = []

# Aplicar las condiciones sobre cada tupla
for row1, row2 in group_pairs:

    if (row1['Strike Price'] <= row1['5% Superior'] and 
        row2['Percentage Difference'] <= percentageDifference):
        
        # Si todas las condiciones se cumplen, añadir la tupla a la lista
        valid_pairs.append((row1, row2))

# Mostrar las tuplas válidas
#for pair in valid_pairs:
#    print(f"Par válido:\n{pair[0]}\n{pair[1]}\n")

for idx, (row1, row2) in enumerate(valid_pairs):
    # Parámetros del Bull Spread
    strike1 = row1['Strike Price']
    strike2 = row2['Strike Price']
    price1 = row1['Último']  # Precio de la opción comprada
    price2 = row2['Último']  # Precio de la opción vendida

    # Calcular el pago del Bull Spread
    precios_subyacentes = np.linspace(strike1 * 0.8, strike2 * 1.2, 100)
    ganancia = np.where(precios_subyacentes < strike1, 0,
                        np.where(precios_subyacentes > strike2, strike2 - strike1,
                                 precios_subyacentes - strike1)) - (price1 - price2)
    
    ganancia_total = ganancia * lotes * 100  # Multiplicar por el número de lotes

    # Graficar el Bull Spread para este par
    plt.figure(figsize=(8, 4))
    plt.plot(precios_subyacentes, ganancia_total, label=f'Bull Spread {strike1} - {strike2}')
    plt.axhline(0, color='black', linestyle='--')
    plt.title(f'{row1["Activo Subyacente"]} - Vencimiento: {row1["Expiration"]} \nBull Spread #{idx + 1}: {strike1} - {strike2}')
    plt.ylabel('Ganancia/Pérdida Total')
    plt.legend()
    plt.grid(True)
    plt.show()

