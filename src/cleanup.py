import pandas as pd
import geopandas as gpd


def read_population():
    results = pd.read_excel('/Users/Dario/Documents/GitHub/GIS_KARTO/data/bevoelkerung/bev.xlsx',
                            sheet_name='data', header=3)
    results = results.dropna(axis=0)

    df = results.loc[~results['GMDNAME'].str.startswith('>>')]
    df = df.loc[~df['GMDNAME'].str.startswith('-')]
    df['GMDNAME'] = df['GMDNAME'].str[6:]
    df['GMDNAME'] = df['GMDNAME'].str[:4]
    df = df.drop(index=0)
    df = df.reset_index(drop=True)
    df['BFS'] = df['GMDNAME'].astype(int)

    return df


def pop_clean(population):
    rename_cols = {
        'BFS': 'BFSNR',
        'Total': 'POP_TOTAL',
        'Total.1': 'POP_CH_TOTAL',
        'Total.2': 'POP_FOREIGN_TOTAL'
    }

    drop_cols = ['GMDNAME', 'Mann', 'Frau',
                 'Mann.1', 'Frau.1', 'Mann.2', 'Frau.2']

    population = population.rename(columns=rename_cols)
    population = population.drop(columns=drop_cols)
    population = population.reindex(
        columns=['BFSNR', 'POP_TOTAL', 'POP_CH_TOTAL', 'POP_FOREIGN_TOTAL'])

    return population


def merge_data(df_left, df_right, on=str):
    df = pd.merge(df_left, df_right, on=on, how='left')
    return df


def export(df_in, filename):
    df_in.to_file(f'../export/master/{filename}.geojson', driver='GeoJSON')


if __name__ == '__main__':
    population = read_population()
    population = pop_clean(population)
    master = gpd.read_file(
        '../export/master/sum_of_bikes.geojson', driver='GeoJSON')
    merged = merge_data(master, population, on='BFSNR')
    export(merged, 'master_table')
