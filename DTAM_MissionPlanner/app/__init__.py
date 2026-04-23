"""DTAM Mission Planner — FastAPI backend + web frontend.

odt_mp 의 미션 계획 GUI 를 그대로 가져오되, AirSim / 시뮬레이터 연결부를
제거하고 대신 DTAM_SDK 를 이용해 3001 (Scheduled Flight) 메시지를 송출한다.
"""
