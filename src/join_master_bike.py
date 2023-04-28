import pandas as pd
import geopandas as gpd
import datetime

now = datetime.datetime.now().date().strftime('%d-%m-%y')


def join_data():
    master = gpd.read_file('../export/master/master_with_acc.geojson')
    bike = pd.read_csv('../export/master/sum_bikes.csv', sep=';')

    bike = bike.rename(
        columns={'BFS': 'GMDNR', 'SUM_Shape_Length': 'SUM_LENGTH'})
    master = master.merge(bike, how='left')
    master = master.rename(columns={'GMDNR': 'BFSNR', 'GMDNAME_x': 'GMDNAME', 'Stimmberechtigte': 'ELEGIBLE_VOTERS', 'Abgegebene Stimmen': 'TOT_VOTES', 'Beteiligung in %': 'PART_PERCENT',
                           'Ja in %': 'YES_IN_PER', 'Gültige Stimmzettel': 'VALID_VOTES', 'Ja': 'YES', 'Nein': 'NO', 'smaller_2': 'ACC_2', '2_to_5': 'ACC_2_5', '5_to_10': 'ACC_5_10', 'FREQUENCY': 'SUM_FREQ'})
    master = master.drop(columns='GMDNAME_y', axis=1)
    master['YES_IN_PER'] = master['YES_IN_PER'].fillna(-1)

    master.to_file(f'../export/master/sum_of_bikes.geojson',
                   driver='GeoJSON', index=False)


if __name__ == '__main__':
    join_data()
