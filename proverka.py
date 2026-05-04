import pandas as pd

df = pd.read_csv("zvezda_cached.csv", sep=";", encoding="utf-8-sig")
print("Колонки:", df.columns.tolist())
print("\nПервые 5 строк:")
print(df[["Модель", "Название", "Цена", "Фото"]].head())