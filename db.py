from influxdb import InfluxDBClient
client = InfluxDBClient(host='localhost', port=8086)
client = InfluxDBClient(host='localhost',
                        port=8086,
                        database='stocks',
                        username='write_user',
                        password='write_user')
client.switch_database("stocks")
# json_body = [
#     {
#         "measurement": "brushEvents",
#         "tags": {
#             "user": "Carol",
#             "brushId": "6c89f539-71c6-490d-a28d-6c5d84c0ee2f"
#         },
#         "time": "2018-03-28T8:01:00Z",
#         "fields": {
#             "duration": 127
#         }
#     },
#     {
#         "measurement": "brushEvents",
#         "tags": {
#             "user": "Carol",
#             "brushId": "6c89f539-71c6-490d-a28d-6c5d84c0ee2f"
#         },
#         "time": "2018-03-29T8:04:00Z",
#         "fields": {
#             "duration": 132
#         }
#     },
#     {
#         "measurement": "brushEvents",
#         "tags": {
#             "user": "Carol",
#             "brushId": "6c89f539-71c6-490d-a28d-6c5d84c0ee2f"
#         },
#         "time": "2018-03-30T8:02:00Z",
#         "fields": {
#             "duration": 129
#         }
#     }
# ]

#client.write_points(json_body)
results = client.query('SELECT "duration" FROM "stocks"."autogen"."brushEvents" WHERE time > now() - 4d ')
print(results.raw)
points = results.get_points(tags={'user':'Carol'})
print(points)

def get_client():
    return client

def insert(json):
    client.write_points(json)

def insert_stock_data():
    pass

