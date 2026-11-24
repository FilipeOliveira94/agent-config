---
name: issue-cycle
description: "Leva uma issue (ou fase) do plano até o PR aberto para o Filipe revisar e fazer o merge. Use quando citarem uma issue, um critério de aceite, uma feature a construir, ou pedirem para planejar, implementar, verificar ou abrir o PR de uma issue."
---

# Ciclo de issue

Uma issue ou fase por vez. O texto de aceite é a definição de pronto: não puxe issues futuras e não mude o aceite durante a construção. As regras gerais (papéis, tamanho da tarefa, gates de revisão e política de modelos) estão em `~/.agents/claude/workflow.md`; o `AGENTS.md` do repositório prevalece no que for específico do projeto, inclusive a seção "Agent workflow".

Ciclo: plan → (grande, perfil `reviewed`: `po-reviewer` no plano) → (grande: aprovação do Filipe) → implementação numa branch nova a partir da `main` atualizada → checks/testes → gates de revisão → commit, push da branch e PR com resumo. O merge é sempre do Filipe: o agente nunca faz merge nem apaga branch.

## Modo: pequena ou grande

O prompt da issue diz qual modo seguir (critério em "Task size" no `workflow.md`, ou no `AGENTS.md` quando o projeto o refina).

- **Pequena:** planeje e implemente direto até o PR.
- **Grande:** planeje e **pare**. Apresente o plano na thread e espere a aprovação do Filipe antes de mexer em código. Incorpore os ajustes que vierem com a aprovação.
- Se, ao planejar, uma tarefa marcada como pequena se mostrar maior, reclassifique para grande, diga por quê e pare para aprovação. Nunca reclassifique de grande para pequena.

## 1. Planejar

Leia a issue, o aceite, o status do projeto (`PROJECT_STATUS.md`/`ROADMAP.md`) e a seção "Agent workflow" do `AGENTS.md`, sem alterar arquivos. Se o projeto não tiver essa seção, pare e peça ao Filipe para defini-la ("Profiles" no `workflow.md`). Defina escopo, fora de escopo, abordagem, riscos e o que uma pessoa consegue fazer quando estiver pronto.

Na tarefa grande de um projeto `reviewed`, rode o `po-reviewer` (modo `plan`) com o ID da issue e o plano, corrija o que ele apontar e mostre o veredito junto com o plano. Na tarefa grande, este plano é o que vai para aprovação: termine o turno aqui.

## 2. Implementar

Atualize a `main` (`git pull`) e crie uma branch nova a partir dela.

Faça a menor mudança que torna o comportamento aceito verdadeiro. Não acrescente confirmação, restrição ou passo que a issue não pediu. Ao extrair lógica repetida ou escolher fronteiras entre módulos, consulte a skill `code-structure`; a arquitetura existente do projeto prevalece.

## 3. Verificar

- Rode os checks e testes do projeto. Check não executado não é aprovação; registre comando e saída.
- Exercite cada comportamento da issue como a pessoa usuária o faria. Comportamento não exercitado não está pronto; diga qual ficou de fora e por quê.
- Um check interno verde não basta se a pessoa vê outra superfície. Olhe essa superfície.

## 4. Revisar (perfil `reviewed`)

Com a branch pronta e os checks rodados:

- `code-reviewer` em toda mudança de código ou config, com a branch base e o objetivo da mudança. Mudança só de docs ou texto pula este gate.
- Os revisores extras que a seção "Agent workflow" listar, quando o gatilho bater.
- Na tarefa grande, depois do `code-reviewer`, o `po-reviewer` (modo `acceptance`) com o ID da issue, a branch base e os checks rodados com as saídas.

Corrija os achados críticos e os critérios NOT MET e rode o revisor de novo. Se o mesmo achado continuar aberto depois de 2 rodadas, pare e relate ao Filipe. Perfil `solo`: pule esta etapa.

## 5. Entregar

Commits convencionais, push da branch e PR com resumo:
- o que foi feito e como cumpre o aceite;
- a classificação, pequena ou grande;
- checks e testes rodados, com as saídas relevantes;
- o veredito final de cada revisor, ou quais gates foram pulados e por quê;
- o que segue aberto ou ficou de fora.

Pare aí. Não faça merge, não apague a branch, não rode CD. Correções pedidas na revisão entram como novos commits na mesma branch.
