import pandas as pd

df = pd.read_csv(
    r"C:\Users\tntma\Work\Cloud_Computing\data\anime-dataset-2023-utf8.csv",
    usecols=['anime_id', 'English name', 'Score', 'Genres', 
             'Episodes', 'Studios', 'Rank', 
             'Popularity', 'Members', 'Synopsis'],
    nrows=5000  # for dev purposes
)

df.rename(columns={"English name": "english_name"}, inplace=True)
print(df.columns.tolist())
print(df.dtypes)
print(df.head(3))

df.to_csv(r"C:\Users\tntma\Work\Cloud_Computing\data\anime_trimmed.csv", index=False)