import csv
with open("part.csv") as f:
    for i in range(0, 16):
        print(f.readline())

    for index, row in enumerate(csv.DictReader(f)):
        print(index, row)