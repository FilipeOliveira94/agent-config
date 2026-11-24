---
name: issue-cycle
description: "Leva uma issue (ou fase) do plano até o PR aberto para o Filipe revisar e fazer o merge. Use quando citarem uma issue, um critério de aceite, uma feature a construir, ou pedirem para planejar, implementar, verificar ou abrir o PR de uma issue."
---

# Ciclo de issue

Uma issue ou fase por vez. O texto de aceite é a definição de pronto: não puxe issues futuras e não mude o aceite durante a construção. As regras gerais (idioma, papéis, tamanho e risco, gates de revisão e política de modelos) estão em `~/.agents/claude/workflow.md`; o `AGENTS.md` do repositório prevalece no que for específico do projeto, inclusive a seção "Agent workflow".

Ciclo: avaliar tamanho e risco → plano → (acima de S + Low: `po-reviewer` no plano, no perfil `reviewed`, e aprovação do Filipe) → implementação numa branch nova a partir da `main` atualizada → checks/testes → gates de revisão → commit, push da branch e PR com resumo. O merge é sempre do Filipe: o agente nunca faz merge nem apaga branch.

## Tamanho e risco

Toda issue tem Size (S, M, L) e Risk (Low, Med, High), na escala do `workflow.md`. Use a nota do roadmap; se não houver, estime no plano com uma linha de justificativa e registre no roadmap no mesmo PR. A nota decide:

- **S + Low:** planeje e implemente direto até o PR.
- **Qualquer outra:** planeje e **pare**. Apresente o plano na thread e espere a aprovação do Filipe antes de mexer em código. Incorpore os ajustes que vierem com a aprovação.
- **Risk High ou Size L:** comece em Opus high (você mesmo troca o esforço da thread; ver "Model policy" no `workflow.md`). Em High, o plano nomeia as regras críticas em jogo e os testes escritos primeiro; em L, o plano propõe a divisão antes.
- Se, ao planejar, a issue se mostrar maior ou mais arriscada, suba a nota, diga por quê e siga o modo novo. Nunca baixe uma nota sem o Filipe.

## 1. Planejar

Leia a issue, o aceite, a nota, o status do projeto (`PROJECT_STATUS.md`/`ROADMAP.md`) e a seção "Agent workflow" do `AGENTS.md`, sem alterar arquivos. Se o projeto não tiver essa seção, pare e peça ao Filipe para defini-la ("Profiles" no `workflow.md`). Defina escopo, fora de escopo, abordagem, riscos e o que uma pessoa consegue fazer quando estiver pronto.

Acima de S + Low num projeto `reviewed`, rode o `po-reviewer` (modo `plan`) com o ID da issue, a nota e o plano, corrija o que ele apontar e mostre o veredito junto com o plano. Acima de S + Low, este plano é o que vai para aprovação: termine o turno aqui.

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
- Os revisores extras que a seção "Agent workflow" listar, quando o gatilho bater. Eles ficam em `.claude/agents/` do projeto.
- Acima de S + Low, depois do `code-reviewer`, o `po-reviewer` (modo `acceptance`) com o ID da issue, a nota, a branch base e os checks rodados com as saídas.

Corrija os achados críticos e os critérios NOT MET e rode o revisor de novo. Se o mesmo achado continuar aberto depois de 2 rodadas, escale conforme a "Model policy" do `workflow.md`: Opus high por conta própria; Fable só com o sim do Filipe. Perfil `solo`: pule esta etapa.

## 5. Entregar

Commits convencionais, push da branch e PR com resumo:
- o que foi feito e como cumpre o aceite;
- a nota (Size e Risk) e se mudou no caminho;
- checks e testes rodados, com as saídas relevantes;
- o veredito final de cada revisor, ou quais gates foram pulados e por quê;
- o que segue aberto ou ficou de fora.

Pare aí. Não faça merge, não apague a branch, não rode CD. Correções pedidas na revisão entram como novos commits na mesma branch.
