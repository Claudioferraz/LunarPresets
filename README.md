# Relatório Fotográfico de Câmeras — v2.2.0

Ferramenta para gerar relatórios fotográficos profissionais a partir de fotos + planilha Excel.

## O que faz
- Lê um Excel com dados de câmeras, presets e IDSAGE
- Lê fotos nomeadas no padrão: `Camera - P01 IDSAGE.jpg`
- Gera um PDF A4 paisagem completo com:
  - Capa
  - Dashboard do projeto
  - Mapa / foto do local
  - Informações de câmeras
  - Desenho da subestação
  - Páginas de fotos organizadas
  - Observações (SEM VISÃO etc.)
  - Página de Aceite
- Opcionalmente move as fotos usadas para `fotos/_usadas/`

## Estrutura de pastas
```
RelatorioCameras/
├── painel.py              (ou RelatorioCameras.exe)
├── main.py
├── config.json
├── Excel.xlsx             (sua planilha)
├── fotos/
│   ├── foto1.jpg
│   ├── foto2.jpg
│   └── _usadas/           (criada automaticamente)
└── saida/
    ├── relatorio.pdf
    └── log_fotos.txt
```

## Como usar
1. Coloque as fotos na pasta `fotos/`
2. Coloque o Excel (ou renomeie para o nome definido no config)
3. Edite o `config.json` (ou use o botão Configurações no painel)
4. Execute o painel e clique em **INICIAR PRODUÇÃO**

## Padrão de nome das fotos
```
NOME_DA_CAMERA - P01 IDSAGE.jpg
```
Exemplos válidos:
- `CAM_01 - P1 12345_DJ.jpg`
- `Camera Norte - P02 EQUIP_ABC.png`

## Colunas esperadas no Excel
- **IDSAGE** (obrigatório)
- **Camera**
- **Preset**
- **FASE**
- **ESTADO**
- Coluna de Observações (qualquer nome que contenha "OBSERV")

## Gerar executável (Windows)
```bash
pip install -r requirements.txt pyinstaller
pyinstaller --onefile --windowed --name "RelatorioCameras" painel.py
```

## Desenvolvedor
Claudio Ibarrola
