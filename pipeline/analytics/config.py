# config.py
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_RAW     = os.path.join(BASE_DIR, '../data/raw')
DATA_PROCESSED = os.path.join(BASE_DIR, '../data/processed')
OUTPUTS      = os.path.join(BASE_DIR, '../outputs/')

MATCH_EXCEL  = os.path.join(DATA_RAW, 'cofc_matches_2025.xlsx')
#PLAYER_PDFS  = os.path.join(DATA_RAW, 'player_reports')
REPORT_DIR   = os.path.join(OUTPUTS, 'reports')
#TEAM_INGEST_DIR = os.path.join(DATA_RAW, 'team_ingest/')
TEAM_INGEST_DIR = DATA_RAW
PLAYER_INGEST_DIR = os.path.join(DATA_RAW, 'player_reports/')
COUG_TABLE_DIR = os.path.join(OUTPUTS, 'coug_table/')
COUG_TABLE_FIGURES = os.path.join(OUTPUTS, 'coug_table/figures')