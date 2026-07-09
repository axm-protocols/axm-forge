<script lang="ts">
  import { greet } from "./greet.js";

  const { name }: { name: string } = $props();
</script>

<p>{greet(name)}</p>
