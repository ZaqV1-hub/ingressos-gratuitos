Para usar o e-mail do Titan neste projeto, deixe estas variáveis assim:

```env
SMTP_HOST=smtp.titan.email
SMTP_PORT=465
SMTP_USERNAME=comercial@seudominio.com.br
SMTP_PASSWORD=sua_senha_do_email
SMTP_FROM_EMAIL=comercial@seudominio.com.br
SMTP_FROM_NAME=Estância Parque Ecológico das Águas
SMTP_USE_SSL=true
EMAIL_SEND_TIMEOUT_SECONDS=20
```

Se o Titan da sua conta estiver configurado com TLS em vez de SSL, use assim:

```env
SMTP_HOST=smtp.titan.email
SMTP_PORT=587
SMTP_USERNAME=comercial@seudominio.com.br
SMTP_PASSWORD=sua_senha_do_email
SMTP_FROM_EMAIL=comercial@seudominio.com.br
SMTP_FROM_NAME=Estância Parque Ecológico das Águas
SMTP_USE_SSL=false
EMAIL_SEND_TIMEOUT_SECONDS=20
```

O sistema agora lê primeiro `SMTP_*`. Se essas variáveis estiverem preenchidas, elas serão usadas automaticamente.
