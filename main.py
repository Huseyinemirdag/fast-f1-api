from fastapi import FastAPI, HTTPException
import fastf1
import json
from fastapi.responses import JSONResponse, Response
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
from fastapi.staticfiles import StaticFiles
import os
import matplotlib.pyplot as plt
import io

app = FastAPI()

F1_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
SPRINT_POINTS = [8, 7, 6, 5, 4, 3, 2, 1]
SPRINT_ROUNDS_2024 = {
    4: "China",
    6: "Miami",
    11: "Austria",
    18: "Austin",
    21: "Brazil",
    23: "Qatar"
}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return {"message": "F1 RESTful API'ye hoş geldiniz!"}

@app.get("/races/{season}")
def get_races(season: int):
    try:
        schedule = fastf1.get_event_schedule(season)
        races = []
        for _, row in schedule.iterrows():
            races.append({
                "round": int(row["RoundNumber"]),
                "name": row["EventName"],
                "country": row["Country"],
                "location": row["Location"],
                "date": str(row["EventDate"])
            })
        return {"season": season, "races": races}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/races/{season}/{round}")
def get_race_detail(season: int, round: int):
    try:
        schedule = fastf1.get_event_schedule(season)
        row = schedule[schedule["RoundNumber"] == round].iloc[0]
        race = {
            "round": int(row["RoundNumber"]),
            "name": row["EventName"],
            "country": row["Country"],
            "location": row["Location"],
            "date": str(row["EventDate"])
        }
        return {"season": season, "race": race}
    except Exception as e:
        raise HTTPException(status_code=404, detail="Yarış bulunamadı: " + str(e))

@app.get("/races/{season}/{round}/results")
def get_race_results(season: int, round: int):
    try:
        session = fastf1.get_session(season, round, "R")
        session.load()
        results = session.results
        if results is None:
            raise HTTPException(status_code=404, detail="Yarış sonucu bulunamadı.")
        race_results = []
        for _, row in results.iterrows():
            race_results.append({
                "position": int(row["Position"]),
                "driver": row["FullName"],
                "abbreviation": row["Abbreviation"],
                "team": row["TeamName"],
                "time": str(row["Time"]),
                "status": row["Status"]
            })
        return {"season": season, "round": round, "results": race_results}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/races/{season}/{round}/qualifying")
def get_qualifying_results(season: int, round: int):
    try:
        session = fastf1.get_session(season, round, "Q")
        session.load()
        results = session.results
        if results is None:
            raise HTTPException(status_code=404, detail="Sıralama sonucu bulunamadı.")
        quali_results = []
        for _, row in results.iterrows():
            quali_results.append({
                "position": int(row["Position"]),
                "driver": row["FullName"],
                "abbreviation": row["Abbreviation"],
                "team": row["TeamName"],
                "q1": str(row.get("Q1", "")),
                "q2": str(row.get("Q2", "")),
                "q3": str(row.get("Q3", ""))
            })
        return {"season": season, "round": round, "results": quali_results}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/races/{season}/{round}/drivers")
def get_race_drivers(season: int, round: int):
    try:
        session = fastf1.get_session(season, round, "R")
        session.load()
        results = session.results
        if results is None:
            raise HTTPException(status_code=404, detail="Yarış sürücüleri bulunamadı.")
        drivers = []
        for _, row in results.iterrows():
            drivers.append({
                "number": row["DriverNumber"],
                "name": row["FullName"],
                "abbreviation": row["Abbreviation"],
                "team": row["TeamName"]
            })
        return {"season": season, "round": round, "drivers": drivers}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/drivers/{season}")
def get_drivers(season: int):
    json_path = f"drivers_{season}.json"
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        raise HTTPException(status_code=404, detail="Sürücü verisi bulunamadı.")

@app.get("/constructors/{season}")
def get_constructors(season: int):
    try:
        schedule = fastf1.get_event_schedule(season)
        all_teams = set()
        for _, row in schedule.iterrows():
            if row.get("EventFormat") not in ["conventional", "sprint"]:
                continue
            try:
                event = fastf1.get_session(season, int(row["RoundNumber"]), "R")
                event.load()
                results = event.results
                if results is not None:
                    for _, driver_row in results.iterrows():
                        all_teams.add(driver_row["TeamName"])
            except Exception:
                continue
        teams = sorted(list(all_teams))
        if not teams:
            raise HTTPException(status_code=404, detail="Takım verisi bulunamadı.")
        return {"season": season, "constructors": teams}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/races/{season}/{round}/lap-times/{driver}")
def get_lap_times(season: int, round: int, driver: str):
    try:
        session = fastf1.get_session(season, round, "R")
        session.load()
        laps = session.laps.pick_driver(driver)
        if laps.empty:
            raise HTTPException(status_code=404, detail="Tur zamanı verisi bulunamadı.")
        lap_times = []
        for _, row in laps.iterrows():
            lap_times.append({
                "lap_number": int(row["LapNumber"]),
                "lap_time": str(row["LapTime"]),
                "position": int(row["Position"]),
                "pit": bool(row["PitInLap"])
            })
        return {"season": season, "round": round, "driver": driver, "lap_times": lap_times}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/races/{season}/{round}/sector-times/{driver}")
def get_sector_times(season: int, round: int, driver: str):
    try:
        session = fastf1.get_session(season, round, "R")
        session.load()
        laps = session.laps.pick_driver(driver)
        if laps.empty:
            raise HTTPException(status_code=404, detail="Sektör zamanı verisi bulunamadı.")
        sector_times = []
        for _, row in laps.iterrows():
            sector_times.append({
                "lap_number": int(row["LapNumber"]),
                "sector1": str(row["Sector1Time"]),
                "sector2": str(row["Sector2Time"]),
                "sector3": str(row["Sector3Time"])
            })
        return {"season": season, "round": round, "driver": driver, "sector_times": sector_times}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/races/{season}/{round}/tyres/{driver}")
def get_tyre_data(season: int, round: int, driver: str):
    try:
        session = fastf1.get_session(season, round, "R")
        session.load()
        laps = session.laps.pick_driver(driver)
        if laps.empty or "Stint" not in laps.columns:
            raise HTTPException(status_code=404, detail="Lastik verisi bulunamadı.")
        tyre_data = []
        for _, row in laps.iterrows():
            tyre_data.append({
                "lap_number": int(row["LapNumber"]),
                "compound": row.get("Compound", None),
                "stint": int(row.get("Stint", 0)),
                "fresh": bool(row.get("FreshTyre", False))
            })
        return {"season": season, "round": round, "driver": driver, "tyre_data": tyre_data}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/races/{season}/{round}/weather")
def get_weather_data(season: int, round: int):
    try:
        session = fastf1.get_session(season, round, "R")
        session.load()
        weather = session.weather_data
        if weather is None or weather.empty:
            raise HTTPException(status_code=404, detail="Hava durumu verisi bulunamadı.")
        weather_list = []
        for _, row in weather.iterrows():
            weather_list.append({
                "time": str(row["Time"]),
                "air_temp": float(row["AirTemp"]),
                "track_temp": float(row["TrackTemp"]),
                "humidity": float(row["Humidity"]),
                "rainfall": float(row["Rainfall"]),
                "wind_speed": float(row["WindSpeed"]),
                "wind_direction": float(row["WindDirection"])
            })
        return {"season": season, "round": round, "weather": weather_list}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/races/{season}/{round}/events")
def get_race_events(season: int, round: int):
    try:
        session = fastf1.get_session(season, round, "R")
        session.load()
        messages = session.race_control_messages
        if messages is None or messages.empty:
            raise HTTPException(status_code=404, detail="Yarış olayı verisi bulunamadı.")
        events = []
        for _, row in messages.iterrows():
            events.append({
                "time": str(row["UTC"]),
                "category": row.get("Category", None),
                "message": row.get("Message", None)
            })
        return {"season": season, "round": round, "events": events}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/standings/drivers/{season}")
def get_driver_standings_local(season: int):
    try:
        schedule = fastf1.get_event_schedule(season)
        driver_points = {}
        driver_names = {}
        no_data_rounds = []
        for _, row in schedule.iterrows():
            if row.get("EventFormat") not in ["conventional", "sprint"]:
                continue
            round_number = int(row["RoundNumber"])
            # Ana yarış (Race)
            try:
                session = fastf1.get_session(season, round_number, "R")
                session.load()
                results = session.results
                fastest_lap_driver = None
                if results is not None:
                    # En hızlı turu bul
                    if "FastestLap" in results.columns and not results["FastestLap"].isnull().all():
                        fastest_lap_row = results.loc[results["FastestLapTime"] == results["FastestLapTime"].min()]
                        if not fastest_lap_row.empty:
                            fastest_lap_driver = fastest_lap_row.iloc[0]["DriverNumber"]
                    race_points_log = []
                    for idx, r in results.iterrows():
                        pos = int(r["Position"])
                        driver_id = r["DriverNumber"]
                        name = r["FullName"]
                        pts = 0
                        if pos <= 10:
                            pts = F1_POINTS[pos-1]
                        # En hızlı tur puanı (ilk 10'da ve fastest lap sahibi)
                        if fastest_lap_driver == driver_id and pos <= 10:
                            pts += 1
                        if pts > 0:
                            driver_points[driver_id] = driver_points.get(driver_id, 0) + pts
                            driver_names[driver_id] = name
                            race_points_log.append((name, pos, pts))
                    print(f"{season} Round {round_number} (Race) puan dağılımı: {race_points_log}")
                else:
                    no_data_rounds.append(f"Race-{round_number}")
            except Exception as e:
                no_data_rounds.append(f"Race-{round_number}")
                continue
            # Sprint
            try:
                session = fastf1.get_session(season, round_number, "S")
                session.load()
                results = session.results
                if results is not None:
                    sprint_points_log = []
                    for idx, r in results.iterrows():
                        pos = int(r["Position"])
                        driver_id = r["DriverNumber"]
                        name = r["FullName"]
                        pts = 0
                        if pos <= 8:
                            pts = SPRINT_POINTS[pos-1]
                        if pts > 0:
                            driver_points[driver_id] = driver_points.get(driver_id, 0) + pts
                            driver_names[driver_id] = name
                            sprint_points_log.append((name, pos, pts))
                    print(f"{season} Round {round_number} (Sprint) puan dağılımı: {sprint_points_log}")
                else:
                    no_data_rounds.append(f"Sprint-{round_number}")
            except Exception as e:
                no_data_rounds.append(f"Sprint-{round_number}")
                continue
        standings = [
            {"driver_id": driver_id, "name": driver_names[driver_id], "points": pts}
            for driver_id, pts in driver_points.items()
        ]
        standings.sort(key=lambda x: x["points"], reverse=True)
        return {"season": season, "driver_standings": standings, "no_data_rounds": no_data_rounds}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/standings/constructors/{season}")
def get_constructor_standings_local(season: int):
    try:
        schedule = fastf1.get_event_schedule(season)
        team_points = {}
        team_names = {}
        no_data_rounds = []
        for _, row in schedule.iterrows():
            if row.get("EventFormat") not in ["conventional", "sprint"]:
                continue
            round_number = int(row["RoundNumber"])
            # Ana yarış (Race)
            try:
                session = fastf1.get_session(season, round_number, "R")
                session.load()
                results = session.results
                fastest_lap_driver = None
                if results is not None:
                    if "FastestLap" in results.columns and not results["FastestLap"].isnull().all():
                        fastest_lap_row = results.loc[results["FastestLapTime"] == results["FastestLapTime"].min()]
                        if not fastest_lap_row.empty:
                            fastest_lap_driver = fastest_lap_row.iloc[0]["DriverNumber"]
                    for idx, r in results.iterrows():
                        pos = int(r["Position"])
                        team = r["TeamName"]
                        driver_id = r["DriverNumber"]
                        pts = 0
                        if pos <= 10:
                            pts = F1_POINTS[pos-1]
                        if fastest_lap_driver == driver_id and pos <= 10:
                            pts += 1
                        if pts > 0:
                            team_points[team] = team_points.get(team, 0) + pts
                            team_names[team] = team
                else:
                    no_data_rounds.append(f"Race-{round_number}")
            except Exception as e:
                no_data_rounds.append(f"Race-{round_number}")
                continue
            # Sprint
            try:
                session = fastf1.get_session(season, round_number, "S")
                session.load()
                results = session.results
                if results is not None:
                    for idx, r in results.iterrows():
                        pos = int(r["Position"])
                        team = r["TeamName"]
                        pts = 0
                        if pos <= 8:
                            pts = SPRINT_POINTS[pos-1]
                        if pts > 0:
                            team_points[team] = team_points.get(team, 0) + pts
                            team_names[team] = team
                else:
                    no_data_rounds.append(f"Sprint-{round_number}")
            except Exception as e:
                no_data_rounds.append(f"Sprint-{round_number}")
                continue
        standings = [
            {"team": team, "points": pts}
            for team, pts in team_points.items()
        ]
        standings.sort(key=lambda x: x["points"], reverse=True)
        return {"season": season, "constructor_standings": standings, "no_data_rounds": no_data_rounds}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/track-map/{season}/{round}")
def get_track_map(season: int, round: int):
    try:
        session = fastf1.get_session(season, round, "R")
        session.load()
        coords = session.get_circuit_info().coordinates
        if coords is None or len(coords) == 0:
            raise HTTPException(status_code=404, detail="Pist haritası bulunamadı.")

        fig, ax = plt.subplots()
        ax.plot(coords[:, 0], coords[:, 1], color='black')
        ax.set_aspect('equal')
        ax.axis('off')

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        buf.seek(0)
        return Response(content=buf.read(), media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sprints/{season}")
def get_sprint_results(season: int):
    try:
        schedule = fastf1.get_event_schedule(season)
        sprint_rounds = schedule[schedule["EventFormat"] == "sprint"]
        all_sprints = []
        for _, row in sprint_rounds.iterrows():
            round_number = int(row["RoundNumber"])
            print(f"Sprint round: {round_number} - {row['EventName']}")
            found = False
            for sprint_code in ["S", "Sprint"]:
                try:
                    print(f"  Deneniyor: get_session({season}, {round_number}, '{sprint_code}')")
                    session = fastf1.get_session(season, round_number, sprint_code)
                    session.load()
                    results = session.results
                    if results is not None:
                        sprint_results = []
                        for idx, r in results.iterrows():
                            pos = int(r["Position"])
                            if pos <= 8:
                                sprint_results.append({
                                    "position": pos,
                                    "driver": r["FullName"],
                                    "abbreviation": r["Abbreviation"],
                                    "team": r["TeamName"]
                                })
                        all_sprints.append({
                            "round": round_number,
                            "event": row["EventName"],
                            "sprint_code": sprint_code,
                            "sprint_results": sprint_results
                        })
                        found = True
                        break
                except Exception as e:
                    print(f"  Hata: {e}")
                    continue
            if not found:
                all_sprints.append({
                    "round": round_number,
                    "event": row["EventName"],
                    "error": "Sprint oturumu bulunamadı veya veri yok."
                })
        return {"season": season, "sprints": all_sprints}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def scrape_f1_sprint_results(season):
    url = f"https://www.formula1.com/en/results.html/{season}/races.html"
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(3)  # Sayfanın yüklenmesini bekle

    # Sprint sekmesini bul ve tıkla
    try:
        sprint_tab = driver.find_element(By.XPATH, "//a[contains(text(), 'Sprint')]")
        sprint_tab.click()
        time.sleep(2)
    except Exception as e:
        driver.quit()
        return {"error": "Sprint sekmesi bulunamadı veya tıklanamadı."}

    # Tabloyu bul ve verileri çek
    results = []
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "table.resultsarchive-table tbody tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) > 0:
                results.append({
                    "position": cols[1].text,
                    "driver": cols[3].text,
                    "team": cols[4].text,
                    "time": cols[6].text,
                    "points": cols[7].text
                })
    except Exception as e:
        driver.quit()
        return {"error": "Sprint sonuçları çekilemedi."}

    driver.quit()
    return {"season": season, "sprint_results": results}

@app.get("/scrape-sprints/{season}")
def scrape_sprints(season: int):
    return scrape_f1_sprint_results(season)

@app.get("/sprints/2024")
def get_2024_sprint_results():
    season = 2024
    all_sprints = []
    for round_number, event_name in SPRINT_ROUNDS_2024.items():
        try:
            session = fastf1.get_session(season, round_number, "S")
            session.load()
            results = session.results
            sprint_results = []
            if results is not None:
                for idx, r in results.iterrows():
                    pos = int(r["Position"])
                    if pos <= 8:
                        sprint_results.append({
                            "position": pos,
                            "driver": r["FullName"],
                            "abbreviation": r["Abbreviation"],
                            "team": r["TeamName"]
                        })
            all_sprints.append({
                "round": round_number,
                "event": event_name,
                "sprint_results": sprint_results
            })
        except Exception as e:
            all_sprints.append({
                "round": round_number,
                "event": event_name,
                "error": str(e)
            })
    return {"season": season, "sprints": all_sprints} 