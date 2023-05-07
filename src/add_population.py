import pandas as pd
import geopandas as gpd


def read_population():
    results = pd.read_excel('../data/bevoelkerung/bev.xlsx',
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


def read_pop_new():
    results = pd.read_csv(
        '../data/bevoelkerung/pop_2021.csv', sep=',', encoding='Latin-1')

    results = results.drop(['Jahr', 'Geschlecht'], axis=1)
    results = results.rename(
        columns={'Kanton (-) / Bezirk (>>) / Gemeinde (......)': 'GMDNAME'})
    df = results.loc[~results['GMDNAME'].str.startswith('>>')]
    df = df.loc[~df['GMDNAME'].str.startswith('-')]
    df['GMDNAME'] = df['GMDNAME'].str[6:]
    df['GMDNAME'] = df['GMDNAME'].str[:4]
    df = df.drop(index=0)
    df = df.reset_index(drop=True)
    df = df.drop(index=len(df)-1)
    df['GMDNAME'] = df['GMDNAME'].astype(int)
    df = df.rename(columns={'GMDNAME': 'BFSNR'})
    df = df.rename(columns={'Bestand am 1. Januar': 'POP_TOTAL'})

    return df


def merge_data(df_left, df_right, on=str):
    df = pd.merge(df_left, df_right, on=on, how='left')
    return df

# TODO: Fix this function


def retype_cols(gdf):
    gdf['ELIGIBLE_VOTERS'] = gdf['ELIGIBLE_VOTERS'].astype(int)
    gdf['TOT_VOTES'] = gdf['TOT_VOTES'].astype(int)
    gdf['PART_PERCENT'] = gdf['PART_PERCENT'].astype(float)
    gdf['VALID_VOTES'] = gdf['VALID_VOTES'].astype(int)
    gdf['YES'] = gdf['YES'].astype(int)
    gdf['NO'] = gdf['NO'].astype(int)
    return gdf


def export(df_in):
    df_in.to_file(f'../export/master/master_acc_bike_pop.geojson',
                  driver='GeoJSON')
    return print("Dataframe exported to ../export/master/master_acc_bike_pop.geojson")


if __name__ == '__main__':
    population = read_pop_new()
    #population = pop_clean(population)
    master = gpd.read_file(
        '../export/master/master_acc_bike.geojson', driver='GeoJSON')
    merged = merge_data(master, population, on='BFSNR')
    # Delete this row, has a bunch of NaNs
    #merged = merged[merged['BFSNR'] != 389]
    export(merged)
