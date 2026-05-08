# Stall Handling

If a work item has no observable progress after its lane-specific timeout:

1. inspect live GitHub state;
2. inspect worker run state/logs;
3. retry only if the failure was transient;
4. reassign only if ownership transfer is explicit;
5. pause the lane if the execution surface is unhealthy;
6. escalate to Pheidon/JT when blocked by human decision or repeated infrastructure failure.

`Blocked` is not terminal. It must carry a blocker reason and next actor.
