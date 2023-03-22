import pandas as pd
import geopandas as gpd
import os


def get_bfs():
    bfs = gpd.read_file('data/shp_bfs/g1g23.shp',
                        geometry='geometry', srs='epsg:2056')
    keep_cols = ['GMDNR', 'GMDNAME', 'BZNR', 'KTNR', 'geometry']
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
    print(get_bfs().head())
    print(get_results().head())


if __name__ == '__main__':
    export_df()
