---
name: issue-cycle
description: "Leva uma issue (ou fase) do plano até o PR aberto para o Filipe revisar e fazer o merge. Use quando citarem uma issue, um critério de aceite, uma feature a construir, ou pedirem para planejar, implementar, verificar ou abrir o PR de uma issue."
---

# Ciclo de issue

Uma issue ou fase por vez. O texto de aceite é a definição de pronto: não puxe issues futuras e não mude o aceite durante a construção. As regras gerais estão na skill `fluxo-dev`; o `AGENTS.md` do repositório prevalece no que for específico do projeto.

Ciclo: plan → implementação numa branch nova a partir da `main` atualizada → checks/testes → commit, push da branch e PR com resumo. O merge é sempre do Filipe: o agente nunca faz merge nem apaga branch.

Exceção: no `open-data-platform`, commits convencionais na `main` local, sem push (o Filipe publica).

## 1. Planejar

Leia a issue, o aceite e o status do projeto (`PROJECT_STATUS.md`/`ROADMAP.md`) sem alterar arquivos. Defina escopo, fora de escopo, abordagem, riscos e o que uma pessoa consegue fazer quando estiver pronto.

## 2. Implementar

Atualize a `main` (`git pull`) e crie uma branch nova a partir dela (no `open-data-platform`, trabalhe na `main` local).

Faça a menor mudança que torna o comportamento aceito verdadeiro. Não acrescente confirmação, restrição ou passo que a issue não pediu. Ao extrair lógica repetida ou escolher fronteiras entre módulos, consulte a skill `code-structure`; a arquitetura existente do projeto prevalece.

## 3. Verificar

- Rode os checks e testes do projeto. Check não executado não é aprovação; registre comando e saída.
- Exercite cada comportamento da issue como a pessoa usuária o faria. Comportamento não exercitado não está pronto; diga qual ficou de fora e por quê.
- Um check interno verde não basta se a pessoa vê outra superfície. Olhe essa superfície.

## 4. Entregar

Commits convencionais, push da branch e PR com resumo:
- o que foi feito e como cumpre o aceite;
- checks e testes rodados, com as saídas relevantes;
- o que segue aberto ou ficou de fora.

No `open-data-platform`, sem push nem PR: informe os hashes dos commits locais e os checks.

Pare aí. Não faça merge, não apague a branch, não rode CD. Correções pedidas na revisão entram como novos commits na mesma branch.
