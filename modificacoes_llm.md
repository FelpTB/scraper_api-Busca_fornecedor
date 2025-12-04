Modificações a serem realizadas.

1) Aumentar o timeout no discovery llm de 20 para 35 seg.
2) Colocar retry no discovery para timeouts ou outros erros com backoff exponencial.
3) Reduzir volume de logs, principalmente logs que mostrem informações do perfil das empresas, como quantidade de produtos coletados, etc. 
4) Em todas chamadas de LLM tanto no processo de discovery como no processo de montagem de perfil deve ser feito balanceamento de carga, para distribuirmos uniformemente a demanda de uso das chamadas em LLM. Indicação: criar um novo arquivo em service que será responsável por distribuir as chamadas tanto para discovery.py quanto para llm.py
5) Verifique se o balanceamento está sendo feito após essas alterações.