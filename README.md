# Discord Ticket Bot (discord.py)
## My Portfolio: pedrovasques.com

Bot simples de tickets com botões + modal:
- Cria canal dentro da categoria do tipo selecionado
- Ajusta permissões (usuário + cargos da equipe)
- Contador incremental por tipo (salvo em `ticket_counters.json`)
- Botão para fechar/arquivar (categoria de arquivo opcional via env)

## Como usar

1) Crie seu `.env` baseado no `.env.example`.

2) Rode:
```bash
python main.py
```

## Observações de segurança
- **NUNCA** publique seu token. Mantenha ele apenas no `.env` (o `.gitignore` já cobre).
- IDs de categorias e cargos ficam todos configuráveis via `.env`.

## Configuração de IDs
- Ative modo desenvolvedor no Discord
- Clique com botão direito na categoria -> **Copy ID**
- Cole no `.env` (somente números)
