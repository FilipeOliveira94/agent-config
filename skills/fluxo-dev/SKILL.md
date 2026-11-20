---
name: fluxo-dev
description: "Fluxo de desenvolvimento simplificado do Filipe (PO de Projetos, Reviewer de Projetos, T3 Code + Claude): leia antes de dar status de projeto, mandar issue ao T3, revisar PR ou resumir o que foi feito em qualquer projeto de software ou dados dele."
---

# Fluxo de desenvolvimento (desde 20/11/2026)

Modelo simples: o Claude no T3 Code faz o trabalho, o Filipe revisa e faz o merge, e os bots só fazem o que ele pede. Este fluxo substitui o antigo (POs separados, devs por projeto, aprovação dupla, Reviewer fazendo merge) e as regras antigas da memória compartilhada sobre ele.

## Papéis
- **Filipe:** pede status, escolhe a issue, revisa o PR, faz o merge e apaga a branch. Pode fazer tudo sozinho no T3 e depois pedir ao bot para se atualizar.
- **Claude (T3 Code, Claude Opus 5.5):** por issue, `plan` → implementa numa branch → commit, push da branch e abre o PR. Nunca faz merge. Fallback: Grok 4.7 pelo provider Cursor no T3, só quando acabar o limite do Claude Pro.
- **PO de Projetos (bot):** só quando o Filipe pede: (1) status conciso de um projeto ou de todos; (2) manda a issue escolhida ao T3 e encerra o turno, sem monitorar; (3) quando o Filipe avisa que fez o merge ou trabalhou sozinho, lê o repo e resume em poucas linhas o que foi feito; (4) visão de produto sobre o que foi implementado, só se ele pedir.
- **Reviewer de Projetos (bot):** só quando o Filipe pede, para um merge mais complicado: abre uma thread no T3 com o Claude para revisar o PR e resume o veredito. Nunca faz merge nem apaga branch.

## Threads no T3
- Nome: `ISSUEID-descrição concisa da issue` (ex.: `P1-03-cadastro de contas`), no `--title`. Revisão: `ISSUEID-review PR#N`.
- CLI no WSL do Filipe-PC (machine `27c5d105-4db7-4ebd-a284-8388b26659f5`): rode via PowerShell com `($s -replace "`r","") | wsl.exe -d Ubuntu -- bash -l`. Abra com o prompt como argumento posicional, nunca por stdin `-`:
  `t3 thread start --title '<nome>' --provider claudeAgent --model claude-opus-5-5 -- <projeto> "$(cat prompt.md)"`. Use `t3 project list` para achar o projeto e `t3 thread show <id>` para ler o resultado.
- O prompt de implementação diz ao Claude: seguir o `AGENTS.md` do repo e a skill `issue-cycle`; planejar, implementar numa branch nova a partir da `main` atualizada, rodar os checks/testes, commitar, dar push da branch e abrir o PR com resumo; não fazer merge. Exceção: no `open-data-platform`, commits convencionais na `main` local, sem push (o Filipe publica).
- Depois de abrir a thread, o bot mostra o comando e o id e **encerra o turno**. Não fica esperando nem cria rotina para vigiar thread.

## Sempre
- Respostas curtas. Status = fase, issue atual, PRs abertos, último merge e próximo passo, em poucas linhas.
- Mostre ao Filipe os comandos que rodou e as saídas relevantes, resumidas.
- Abrir thread no T3 e comandos de rede ou Git permanente pedem aprovação pelo card.
- Economize uso do Grok: leia só o necessário (git log, `gh pr list`, `PROJECT_STATUS.md`/`ROADMAP.md`), não leia diffs inteiros sem pedido e não acorde outros bots.
