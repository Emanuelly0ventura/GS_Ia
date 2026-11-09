from pydantic import BaseModel

class RespostaSaude(BaseModel):
    status: str
    servico: str

class RespostaProntidao(BaseModel):
    status: str
    banco: str
