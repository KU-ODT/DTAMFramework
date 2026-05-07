/* telemetry.js — DTAM Mission Planner stub.
 *
 * odt_mp 는 AirSim 텔레메트리를 WebSocket 으로 수신해서 지도 위 비행체
 * 아이콘을 움직였지만, DTAM Mission Planner 는 오로지 3001 송신만을
 * 담당하므로 텔레메트리 기능은 사용하지 않는다. 다른 JS 들이
 * `ODT.Telemetry?.xxx?.()` 패턴으로 optional chaining 하여 호출하는
 * 메서드들만 no-op 으로 노출해 둔다.
 */
window.ODT = window.ODT || {};

ODT.Telemetry = (function () {
  function init() {}
  function openRealtimeChannel() { return Promise.resolve(false); }
  function closeRealtimeChannel() {}
  function resetSimulationView() {}

  return {
    init,
    openRealtimeChannel,
    closeRealtimeChannel,
    resetSimulationView,
  };
})();
