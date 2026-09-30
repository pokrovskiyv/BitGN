# Experimental ECOM adapter

Reviewed for repository publication on 2026-09-30. The existing filesystem domain remains the default. Select the experimental adapter explicitly with `BITGN_DOMAIN=ecom` and a compatible benchmark configuration. Unknown `BITGN_DOMAIN` values fail instead of silently selecting another domain.

The adapter implements the existing `DomainProtocol` using the generated `bitgn.vm.ecom` SDK. The paired SDK and lockfile update includes both PCM and ECOM schemas. It adds tree/find/search/list/read/write/delete/stat/exec/answer mappings; commands execute inside the benchmark runtime when a real run is explicitly started.

Offline checks can verify request mapping, formatting, domain selection and the existing PAC synthetic gauntlet. They do not establish live benchmark performance, policy completeness, security against unseen tasks or acceptance by the platform. ECOM-specific deterministic policy for arbitrary `exec` side effects remains unimplemented; this adapter is experimental and is not a production commerce integration.

`sample_tasks.py` keeps its existing playground behavior. There is no automatic run-based reconnaissance or forced run submission in this change. Real benchmark runs and model calls consume external resources and must be deliberately invoked.

The A-Evolve wrappers also retain task descriptions and agent step metrics in trajectories for diagnosis. Treat trajectories as task data: inspect them before sharing. The [SkillOpt adaptation proposal](superpowers/specs/2026-05-28-skillopt-pcdred-adaptation.md) records the implemented evidence-export phase and separately identifies unimplemented optimizer work.
