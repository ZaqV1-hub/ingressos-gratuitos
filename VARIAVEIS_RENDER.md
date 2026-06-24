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
PANEL_USERNAME=operador2894
PANEL_PASSWORD=estancia1907
FIREBASE_SERVICE_ACCOUNT_JSON_BASE64=cole_aqui_o_base64_da_chave_do_firebase
SMTP_HOST=smtp.titan.email
SMTP_PORT=465
SMTP_USERNAME=seu_email_titan@seudominio.com.br
SMTP_PASSWORD=sua_senha_do_titan
SMTP_FROM_EMAIL=seu_email_titan@seudominio.com.br
SMTP_FROM_NAME=Estância Parque Ecológico das Águas
SMTP_USE_SSL=true
EMAIL_SEND_TIMEOUT_SECONDS=20
```

Se quiser importar tudo de uma vez no Render, você também pode montar um `.env` local com esse conteúdo e colar lá.

Depois de atualizar as variáveis, faça um novo deploy manual no Render para ele aplicar as mudanças.
