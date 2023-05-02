import pandas as pd
import geopandas as gpd
import datetime

now = datetime.datetime.now().date().strftime('%d-%m-%y')


def join_data():
    master = gpd.read_file('../export/master/master_with_accidents.geojson')
    bike = pd.read_csv('../export/velo/sum_bikes.csv', sep=';')

    bike = bike.rename(
        columns={'BFS': 'GMDNR', 'SUM_Shape_Length': 'SUM_LENGTH'})
    master = master.merge(bike, how='left')
    master = master.rename(columns={'GMDNR': 'BFSNR', 'GMDNAME_x': 'GMDNAME', 'Stimmberechtigte': 'ELIGIBLE_VOTERS', 'Abgegebene Stimmen': 'TOT_VOTES', 'Beteiligung in %': 'PART_PERCENT',
                           'Ja in %': 'YES_IN_PER', 'Gültige Stimmzettel': 'VALID_VOTES', 'Ja': 'YES', 'Nein': 'NO', 'FREQUENCY': 'SUM_FREQ'})
    master = master.drop(columns='GMDNAME_y', axis=1)
    master['YES_IN_PER'] = master['YES_IN_PER'].fillna(0)
    master['ACCIDENTS'] = master['ACCIDENTS'].fillna(0)

    master.to_file(f'../export/master/master_acc_bike.geojson',
                   driver='GeoJSON', index=False)
    print('Dataframe exported...')


if __name__ == '__main__':
    join_data()
