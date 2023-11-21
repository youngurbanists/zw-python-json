import csv
from collections import defaultdict
import json
import os
from typing import List
from pathlib import Path
import shutil
from pydantic import BaseModel, ConfigDict

class Coordinates(BaseModel):
    latitude: float
    longitude: float

class Category(BaseModel):
    name: str
    longDescription: str
    rating: str
    notes: str = ""

class BoundingBox(BaseModel):
    southWest: Coordinates
    northEast: Coordinates

class Suburb(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: str
    name: str
    vectorUrl: str
    numberOfCrossings: int
    overallRating: str
    boundingBox: dict
    # Use Coordinates class for the 'southWest' and 'northEast' properties
    boundingBox: BoundingBox

class HumanReadableLocation(BaseModel):
    suburb: str
    crossingStreet: str
    nearbyStreets: List[str]

class Safety(BaseModel):
    rating: str
    categories: List[Category]

class Responsiveness(BaseModel):
    rating: str
    categories: List[Category]

class Crossing(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: str
    humanReadableLocation: HumanReadableLocation
    coordinates: Coordinates
    overallRating: str
    responsiveness: Responsiveness
    safety: Safety
    photoUrls: List[str]

def read_suburbs_from_csv(csv_path) -> List[Suburb]:
    # Create a list to store Suburb instances
    suburbs = []

    # Iterate through each row in the DataFrame
    with open(csv_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                # Create a dictionary from the row and pass it to the Suburb model
                suburb_data = {
                    "id": row["id"],
                    "name": row["name"],
                    "vectorUrl": row["vectorUrl"],
                    "numberOfCrossings": row["numberOfCrossings"],
                    "overallRating": row["overallRating"],
                    "boundingBox": {
                        "southWest": {
                            "latitude": row["southWestLat"],
                            "longitude": row["southWestLng"],
                        },
                        "northEast": {
                            "latitude": row["northEastLat"],
                            "longitude": row["northEastLng"],
                        },
                    },
                }

                suburb = Suburb(**suburb_data)
                suburbs.append(suburb)
            except ValidationError as e:
                print(f"Error processing row {index + 2}: {e}")

    return suburbs

def read_crossings_from_csv(csv_path) -> List[Crossing]:
    # Create a list to store Crossing instances
    crossings = []

    # Iterate through each row in the DataFrame
    with open(csv_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                # Create a dictionary from the row and pass it to the Crossing model
                crossing_data = {
                    "id": row["id"],
                    "humanReadableLocation": HumanReadableLocation(**{
                        "suburb": row["suburb"],
                        "crossingStreet": row["crossingStreet"],
                        "nearbyStreets": [street.strip() for street in row["nearbyStreets"].split(",")]
                    }),
                    "coordinates": {
                        "latitude": row["lat"],
                        "longitude": row["lng"],
                    },
                    "overallRating": row["overallRating"],
                    "responsiveness": Responsiveness(**{
                        "rating": row["responsivenessRating"],
                        "categories": [
                            {
                                "name": "Short Wait Time",
                                "longDescription": "Does the crossing respond quickly after a pedestrian pushes the button, or are pedestrians sometimes required to wait for ages",
                                "rating": row["shortWaitTime"],
                            },
                            {
                                "name": "Buttons Work",
                                "longDescription": "Do buttons on both ends work when pressed",
                                "rating": row["buttonsWork"],
                            },
                            {
                                "name": "Crossing Time",
                                "longDescription": "Do pedestrians have enough time to cross the entire roadway comfortably",
                                "rating": row["crossingTime"],
                            },
                        ],
                    }),
                    "safety": Safety(**{
                        "rating": row["safetyRating"],
                        "categories": [
                            {
                                "name": "Traffic Calming",
                                "longDescription": "Is there physical infrastructure which encourages cars to slow down. Speed bumps, road narrowings, chicanes, etc.",
                                "rating": row["trafficCalming"]
                            },
                            {
                                "name": "Visibility",
                                "longDescription": "Are pedestrians, and the crossing visible to motorists or do trees/parked cars obscure them",
                                "rating": row["visibility"],
                            },
                            {
                                "name": "Signage",
                                "longDescription": "Are there signs and paint warning motorists of the pedestrian crossing",
                                "rating": row["signage"],
                            },
                            {
                                "name": "accessibility",
                                "longDescription": "Is it easy for everyone to cross here. Curb cuts, tactile paving, audible buttons.",
                                "rating": row["accessibility"],
                            },
                        ],
                    }),
                    "photoUrls": [],  # You may need to add this based on your data
                }

                crossing = Crossing(**crossing_data)
                crossings.append(crossing)
            except ValidationError as e:
                print(f"Error processing row {index + 2}: {e}")
    return crossings

def build_api_v1(output_dir: Path):
    api_dir = output_dir / "v1"
    if not os.path.exists(api_dir):
        os.makedirs(api_dir)

    # OpenApi
    shutil.copy('openapi.yaml', api_dir / 'openapi.yaml')

    # Index
    shutil.copy('index.html', api_dir / 'index.html')

    suburbs = read_suburbs_from_csv("suburbs.csv")
    crossings = read_crossings_from_csv("crossings.csv")
    crossings_by_suburb = defaultdict(lambda: [])
    for crossing in crossings:
        crossings_by_suburb[crossing.humanReadableLocation.suburb].append(crossing)

    # Suburbs
    suburb_dir = api_dir / "suburbs"
    suburb_dir.mkdir(parents=True, exist_ok=True)
    # Root suburbs json file
    with (api_dir / "suburbs.json").open("w") as root_suburb_file:
        json.dump([suburb.model_dump() for suburb in suburbs], root_suburb_file, indent=2)

    # Individual suburb jsons with all the stops
    for suburb in suburbs:
        with (suburb_dir / f"{suburb.id}.json").open("w") as suburb_file:
            json.dump({
                        "suburb": suburb.model_dump(),
                        "crossings": [crossing.model_dump() for crossing in crossings_by_suburb[suburb.id]]
                      }, suburb_file, indent=2)

    # Crossings
    crossing_dir = api_dir / "crossings"
    crossing_dir.mkdir(parents=True, exist_ok=True)
    # Root crossings file
    with (api_dir / "crossings.json").open("w") as root_crossing_file:
        json.dump([crossing.model_dump() for crossing in crossings], root_crossing_file, indent=2)

    # Individual crossing jsons
    for crossing in crossings:
        with (crossing_dir / f"{crossing.id}.json").open("w") as suburb_file:
            json.dump(crossing.model_dump(), suburb_file, indent=2)

def copy_static_files(output_dir: Path):
    shutil.copytree("static", str(output_dir / "static"))

if __name__ == "__main__":
    output_dir = Path("_site/")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    copy_static_files(output_dir)
    build_api_v1(output_dir)
