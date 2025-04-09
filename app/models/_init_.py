# app/models/__init__.py
from app.extensions import db

# 导入模型类以便其他地方可以直接从models导入
from app.models.user import User
from app.models.regulation import (
    LegalRegulation, LegalRegulationVersion, 
    LegalStructure, LegalCause, LegalPunishment
)