# Sistema simples de reservas

Sistema local para cadastro de reservas de ingresso para um único dia, com titular, acompanhantes, exportação em Excel e painel separado.

No modo local, os dados ficam em [work/data/reservas.json](C:/Users/Rincao-TI1/Documents/Codex/2026-06-18/eu-quero-criar-um-sistemazinho-de/work/data/reservas.json).

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abra `http://127.0.0.1:5001/reserva`.

No Windows, você também pode abrir `iniciar.bat`.

Se quiser usar variáveis de ambiente, copie a base de [.env.example](C:/Users/Rincao-TI1/Documents/Codex/2026-06-18/eu-quero-criar-um-sistemazinho-de/.env.example).

## Rotas

`/` redireciona para `/reserva`.

`/reserva` abre o formulário de reserva.

`/painel` abre o painel com busca, totais e exportação Excel.

## Armazenamento

Por padrão, o projeto usa arquivo local JSON:

```env
STORAGE_BACKEND=local
```

Se quiser publicar com Firebase Firestore, use:

```env
STORAGE_BACKEND=firebase
FIREBASE_SERVICE_ACCOUNT_FILE=caminho/do/serviceAccount.json
```

ou:

```env
STORAGE_BACKEND=firebase
FIREBASE_SERVICE_ACCOUNT_JSON_BASE64=seu_json_em_base64
SECRET_KEY=uma_chave_aleatoria
```

## Publicação no Render

O projeto já inclui [render.yaml](C:/Users/Rincao-TI1/Documents/Codex/2026-06-18/eu-quero-criar-um-sistemazinho-de/render.yaml) para facilitar a publicação.

O fluxo mais simples fica assim:

1. Criar um projeto no Firebase e ativar o Firestore.
2. Gerar uma chave de conta de serviço no Firebase ou Google Cloud.
3. Converter o JSON da conta de serviço para Base64.
4. Subir o projeto no GitHub.
5. Criar o serviço no Render apontando para esse repositório.
6. No Render, manter `STORAGE_BACKEND=firebase` e preencher `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64`.

Exemplo para converter o JSON em Base64 no PowerShell:

```powershell
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Content .\serviceAccount.json -Raw)))
```

Se preferir, use o arquivo [gerar_firebase_base64.ps1](C:/Users/Rincao-TI1/Documents/Codex/2026-06-18/eu-quero-criar-um-sistemazinho-de/gerar_firebase_base64.ps1).

## E-mail por SMTP

Para ativar o envio de confirmação por e-mail, configure:

```env
SMTP_HOST=smtp.titan.email
SMTP_PORT=465
SMTP_USERNAME=seu-email
SMTP_PASSWORD=sua-senha
SMTP_FROM_EMAIL=seu-email
SMTP_FROM_NAME=Estância Parque Ecológico das Águas
SMTP_USE_SSL=true
EMAIL_SEND_TIMEOUT_SECONDS=20
```

O projeto ainda aceita as variáveis antigas `ZOHO_SMTP_*`, mas agora a prioridade é sempre das variáveis `SMTP_*`.

## Publicação em VM Windows com IIS

Para rodar em VM Windows com IIS, o projeto usa dois componentes:

1. Um processo Python local escutando em `127.0.0.1:5001`.
2. Um `web.config` no IIS fazendo proxy reverso para essa porta.

O arquivo [web.config](C:/Users/Rincao-TI1/Documents/Codex/2026-06-18/eu-quero-criar-um-sistemazinho-de/web.config) já está no repositório e aponta para `http://127.0.0.1:5001`.
O arquivo [iniciar_servico.bat](C:/Users/Rincao-TI1/Documents/Codex/2026-06-18/eu-quero-criar-um-sistemazinho-de/iniciar_servico.bat) sobe o app com `waitress`, que é mais estável para serviço Windows do que o servidor de desenvolvimento do Flask.

Depois de atualizar o código na VM, rode:

```powershell
cd C:\Sites\ingressos-gratuitos
git pull origin main
iisreset
```

Se o serviço do `nssm` já estiver configurado apontando para o comando antigo, recrie ele assim:

```powershell
cd C:\Sites\ingressos-gratuitos
nssm stop IngressosGratuitos
nssm remove IngressosGratuitos confirm
nssm install IngressosGratuitos C:\Windows\System32\cmd.exe /c C:\Sites\ingressos-gratuitos\iniciar_servico.bat
nssm set IngressosGratuitos AppDirectory C:\Sites\ingressos-gratuitos
nssm set IngressosGratuitos Start SERVICE_AUTO_START
nssm start IngressosGratuitos
iisreset
```

Se `http://127.0.0.1:5001/reserva` der conexão recusada, o problema é o processo do app não iniciado. Se o `5001` abrir e o domínio continuar em `502`, aí o problema está no IIS, no `web.config` ou no ARR.

## Observação sobre o plano Free do Render

No plano free, a instância pode entrar em repouso por inatividade. Quando alguém acessa depois disso, o primeiro carregamento pode demorar dezenas de segundos enquanto o serviço volta a subir. Esse comportamento é normal no free do Render. Para evitar isso de vez, só mudando para um plano pago.
