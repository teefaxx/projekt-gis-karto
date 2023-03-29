import pandas as pd
import geopandas as gpd
import os


def get_bfs():
    # Reads in the BFS Shapegile and keeps the needed columns
    bfs = gpd.read_file('/Users/Dario/Documents/GitHub/GIS_KARTO/data/shp_bfs/g1g23_encl.shp',
                        geometry='geometry', srs='epsg:2056')
    keep_cols = ['GMDNR', 'GMDNAME', 'BZNR',
                 'KTNR', 'E_CNTR', 'N_CNTR', 'geometry']
    bfs = bfs.drop(
        columns=[col for col in bfs.columns if col not in keep_cols])

    return bfs


def get_results():
    # Reads in the Results of the vote
    results = pd.read_excel('/Users/Dario/Documents/GitHub/GIS_KARTO/data/Results/Resultate.xlsx',
                            sheet_name='data', header=0)
    results = results.dropna(axis=0)

    df = results.loc[~results['GMDNAME'].str.startswith('>>')]
    df = df.loc[~df['GMDNAME'].str.startswith('-')]
    df['GMDNAME'] = df['GMDNAME'].str[6:]
    df = df.drop(index=0)
    df['GMDNR'] = df['GMDNR'].astype(int)

    df_out = gpd.GeoDataFrame(df)

    return df_out


# def export_df():
    # Exports the dataframes separately to csv
    #get_bfs().to_csv('export/results/bfs_data.csv', sep=';', index=False)
    #get_results().to_csv('export/results/results.csv', sep=';', index=False)

    # return print('Dateframes (bfs and results) created and exported...')


def export_merged_df(df_in):
    #df_in.to_csv('data.csv', index=False)
    df_in.to_file('../../export/master.geojson', driver='GeoJSON')
    return print('Dataframes (merged) exported...')


def merge_data(bfs, results):
    #bfs = pd.read_csv('export/results/bfs_data.csv', sep=';')
    #results = pd.read_csv('export/results/results.csv', sep=';')
    merged_df = pd.merge(results, bfs, on=['GMDNR'])
    merged_gp = gpd.GeoDataFrame(
        merged_df, crs='epsg:2056', geometry='geometry')

    return merged_gp


if __name__ == '__main__':
    # export_df()
    export_merged_df(merge_data(get_bfs(), get_results()))
