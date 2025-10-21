# Ze Partners - Como rodar

## 1) Criar e ativar venv
python3 -m venv .venv
source .venv/bin/activate

## 2) Instalar dependências
pip install -r requirements.txt

## 3) Executar aplicação
uvicorn app:app --reload --host 0.0.0.0 --port 8000

## 4) Testar
- Swagger UI: http://127.0.0.1:8000/docs
- Exemplo de POST:
  curl -X POST "http://127.0.0.1:8000/partners" -H "Content-Type: application/json" -d @sample_partner.json
