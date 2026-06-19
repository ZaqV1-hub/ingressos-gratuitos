# Variáveis do Render

Use estas variáveis no serviço do Render.

Build Command:
`pip install -r requirements.txt`

Start Command:
`python app.py`

Root Directory:
deixe vazio

Variáveis:

```env
PYTHON_VERSION=3.13.5
STORAGE_BACKEND=firebase
APP_UTC_OFFSET_HOURS=-3
SECRET_KEY=gere-uma-chave-segura
PANEL_USERNAME=operador5979
PANEL_PASSWORD=reservas10
FIREBASE_SERVICE_ACCOUNT_JSON_BASE64=cole_aqui_o_base64_da_chave_do_firebase
ZOHO_SMTP_HOST=smtp.zoho.com
ZOHO_SMTP_PORT=465
ZOHO_SMTP_USERNAME=ingressos@cluberincao.com.br
ZOHO_SMTP_PASSWORD=sua_senha_zoho
ZOHO_SMTP_FROM_EMAIL=ingressos@cluberincao.com.br
ZOHO_SMTP_FROM_NAME=Clube Rincão
ZOHO_SMTP_USE_SSL=true
```

Se quiser importar tudo de uma vez no Render, você também pode usar o arquivo local:

`outputs/render.env`

Depois de atualizar as variáveis, faça um novo deploy manual no Render para ele aplicar as mudanças.
