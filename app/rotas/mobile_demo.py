from fastapi import APIRouter

roteador = APIRouter(prefix="/api/v1/mobile/demo", tags=["Mobile — dados predefinidos"] )

@roteador.get("/snapshot", summary="Snapshot estável para telas de demonstração mobile")
def snapshot():
    return {
        "dataMode": "PREDEFINED_DEMO",
        "producer": {"id": "demo-producer", "name": "Produtor Demonstração"},
        "properties": [{"id": "demo-property", "name": "Sítio Boa Esperança", "city": "Carapicuíba", "state": "SP", "areaHectares": 0.5, "fields": [{"id": "field-01", "name": "Canteiro 01", "soilType": "SOLO_FICTICIO", "crops": [{"name": "Alface", "variety": "Crespa", "growthStage": "VEGETATIVE"}]}, {"id": "field-02", "name": "Canteiro 02", "soilType": "SOLO_FICTICIO", "crops": [{"name": "Alface", "variety": "Americana", "growthStage": "VEGETATIVE"}]}]}],
        "indicators": {"temperaturaAr": {"value": 29.5, "unit": "°C", "sensor": "DHT22"}, "umidadeAr": {"value": 64.0, "unit": "%", "sensor": "DHT22"}, "luminosidade": {"value": 780, "unit": "ADC", "sensor": "LDR"}},
        "notice": "Conteúdo fixo de demonstração; não representa leitura atual do simulador nem condição agrícola real."
    }
