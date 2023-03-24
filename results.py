import pandas as pd
import geopandas as gpd
import os


def get_bfs():
    bfs = gpd.read_file('data/shp_bfs/g1g23.shp',
                        geometry='geometry', srs='epsg:2056')
    keep_cols = ['GMDNR', 'GMDNAME', 'BZNR',
                 'KTNR', 'E_CNTR', 'N_CNTR', 'geometry']
    bfs = bfs.drop(
        columns=[col for col in bfs.columns if col not in keep_cols])

    return bfs


def get_results():
    results = pd.read_excel('data/Results/Resultate.xlsx',
                            sheet_name='data', header=0)
    results = results.dropna(axis=0)

    df = results.loc[~results['GMDNAME'].str.startswith('>>')]
    df = df.loc[~df['GMDNAME'].str.startswith('-')]
    df['GMDNAME'] = df['GMDNAME'].str[6:]
    df = df.drop(index=0)
    df['GMDNR'] = df['GMDNR'].astype(int)

    return df


def export_df():
    get_bfs().to_csv('export/results/bfs_data.csv', sep=';', index=False)
    get_results().to_csv('export/results/results.csv', sep=';', index=False)

    return print('Dateframes (bfs and results) created and exported...')


def export_merged_df(df_in):
    df_in.to_csv('data.csv', index=False)

    return print('Dataframes (merged) exported...')


def merge_data():
    bfs = pd.read_csv('export/results/bfs_data.csv', sep=';')
    results = pd.read_csv('export/results/results.csv', sep=';')
    merged_df = pd.merge(results, bfs, on=['GMDNR'])

    return merged_df


if __name__ == '__main__':
    export_df()
    export_merged_df(merge_data())
