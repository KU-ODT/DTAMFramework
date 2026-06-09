"""High-level DTAM SDK facade.

``DtamClient`` is the API intended for module developers:

* set the remote module IP once,
* start a listener when this module should receive data,
* call ``push_*`` or ``send`` with a validated message dict.

Ports are hidden behind the project convention: UDP uses ``base_port`` and TCP
uses ``base_port + 1``. The default base port is 17000.
"""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from ._config import DtamNetworkConfig, get_config, load_network_config
from ._listener import DtamListener
from ._result import PushResult
from .samples import sample_camera_image_bytes, sample_payload


Callback = Callable[[Any], None]
SendCallback = Callable[[PushResult], None]


@dataclass(frozen=True)
class MessageSpec:
    mid: str
    alias: str
    sender_name: str
    callback_name: str
    protocol: str


MESSAGE_SPECS: Dict[str, MessageSpec] = {
    "0001": MessageSpec("0001", "module_setting_info", "push_module_setting_info", "on_module_setting_info", "udp"),
    "0002": MessageSpec("0002", "module_status", "push_module_status", "on_module_status", "udp"),
    "0003": MessageSpec("0003", "common_time_info", "push_common_time_info", "on_common_time_info", "udp"),
    "1001": MessageSpec("1001", "sim_mode_setup", "push_sim_mode_setup", "on_sim_mode_setup", "udp"),
    "1002": MessageSpec("1002", "simulation_setup", "push_simulation_setup", "on_simulation_setup", "udp"),
    "1003": MessageSpec("1003", "scenario_setup", "push_scenario_setup", "on_scenario_setup", "udp"),
    "2001": MessageSpec("2001", "flight_plan_request", "push_flight_plan_request", "on_flight_plan_request", "tcp"),
    "2002": MessageSpec("2002", "dtam_execute", "push_dtam_execute", "on_dtam_execute", "tcp"),
    "3001": MessageSpec("3001", "scheduled_flight", "push_scheduled_flight", "on_scheduled_flight", "tcp"),
    "3002": MessageSpec("3002", "strategic_separation", "push_strategic_separation", "on_strategic_separation", "tcp"),
    "3003": MessageSpec("3003", "tactical_separation", "push_tactical_separation", "on_tactical_separation", "tcp"),
    "4001": MessageSpec("4001", "vehicle_status", "push_vehicle_status", "on_vehicle_status", "udp"),
    "4101": MessageSpec("4101", "camera_image", "push_camera_image", "on_camera_image", "tcp"),
}


_ALIASES: Dict[str, str] = {}
for _mid, _spec in MESSAGE_SPECS.items():
    _ALIASES[_mid] = _mid
    _ALIASES[_spec.alias] = _mid
    _ALIASES[_spec.alias.replace("_", "")] = _mid
    _ALIASES[_spec.sender_name] = _mid
    _ALIASES[_spec.sender_name.removeprefix("push_")] = _mid
    _ALIASES[_spec.callback_name.removeprefix("on_")] = _mid


_CALLBACK_NAMES = {spec.callback_name for spec in MESSAGE_SPECS.values()} | {"on_unknown"}


def _resolve_message(message: str | int) -> MessageSpec:
    key = str(message).strip().lower().replace("-", "_").replace(" ", "_")
    mid = _ALIASES.get(key)
    if mid is None:
        compact = key.replace("_", "")
        mid = _ALIASES.get(compact)
    if mid is None:
        known = ", ".join(sorted(MESSAGE_SPECS))
        raise ValueError(f"Unknown DTAM message '{message}'. Known IDs: {known}")
    return MESSAGE_SPECS[mid]


def _resolve_ports(
    *,
    base_port: int | None = None,
    udp_port: int | None = None,
    tcp_port: int | None = None,
) -> tuple[int, int]:
    cfg = get_config()
    if base_port is not None:
        udp = int(base_port)
        tcp = int(tcp_port) if tcp_port is not None else udp + 1
        return udp, tcp

    udp = int(udp_port) if udp_port is not None else cfg.udp_port
    if tcp_port is not None:
        tcp = int(tcp_port)
    elif udp_port is not None:
        tcp = udp + 1
    else:
        tcp = cfg.tcp_port
    return udp, tcp


def _sender(name: str) -> Callable[..., PushResult]:
    from . import msg as msg_module

    return getattr(msg_module, name)


class DtamClient:
    """IP-first facade for DTAM module communication.

    Example:

        client = DtamClient("192.168.10.20")
        client.on_vehicle_status = lambda msg: print(msg.to_dict())
        client.listen()
        client.push_vehicle_status(data)
    """

    def __init__(
        self,
        target_ip: str | None = None,
        *,
        bind_ip: str = "0.0.0.0",
        base_port: int | None = None,
        udp_port: int | None = None,
        tcp_port: int | None = None,
        target_base_port: int | None = None,
        target_udp_port: int | None = None,
        target_tcp_port: int | None = None,
        auto_listen: bool = False,
        send_workers: int = 4,
    ) -> None:
        cfg = get_config()
        my_udp, my_tcp = _resolve_ports(
            base_port=base_port,
            udp_port=udp_port,
            tcp_port=tcp_port,
        )
        has_peer_override = (
            target_base_port is not None
            or target_udp_port is not None
            or target_tcp_port is not None
        )
        peer_base = target_base_port if has_peer_override else base_port
        peer_udp_arg = target_udp_port if has_peer_override else udp_port
        peer_tcp_arg = target_tcp_port if has_peer_override else tcp_port
        peer_udp, peer_tcp = _resolve_ports(
            base_port=peer_base,
            udp_port=peer_udp_arg,
            tcp_port=peer_tcp_arg,
        )
        self.name = ""
        self.my_ip = bind_ip
        self.my_udp_port = my_udp
        self.my_tcp_port = my_tcp
        self.peer_ip = target_ip or cfg.server_ip
        self.peer_udp_port = peer_udp
        self.peer_tcp_port = peer_tcp
        self.bind_ip = self.my_ip
        self.target_ip = self.peer_ip
        self.udp_port = self.my_udp_port
        self.tcp_port = self.my_tcp_port
        self.on_send_result: Optional[SendCallback] = None
        self.on_send_error: Optional[SendCallback] = None
        self._send_executor = ThreadPoolExecutor(
            max_workers=max(1, int(send_workers)),
            thread_name_prefix="dtam-send",
        )
        self._listener = DtamListener(
            bind_ip=self.my_ip,
            udp_port=self.my_udp_port,
            tcp_port=self.my_tcp_port,
        )
        if auto_listen:
            self.listen(block=False)

    @classmethod
    def module(
        cls,
        *,
        my_ip: str = "0.0.0.0",
        my_port: int = 17000,
        peer_ip: str = "127.0.0.1",
        peer_port: int = 17000,
        my_tcp_port: int | None = None,
        peer_tcp_port: int | None = None,
        auto_listen: bool = True,
        send_workers: int = 4,
    ) -> "DtamClient":
        """Create a client with explicit local and peer endpoints.

        ``my_port`` and ``peer_port`` are UDP ports. TCP is automatically
        ``port + 1`` unless the matching ``*_tcp_port`` is provided.
        """
        return cls(
            peer_ip,
            bind_ip=my_ip,
            base_port=my_port,
            tcp_port=my_tcp_port,
            target_base_port=peer_port,
            target_tcp_port=peer_tcp_port,
            auto_listen=auto_listen,
            send_workers=send_workers,
        )

    @classmethod
    def from_config(
        cls,
        config: str | DtamNetworkConfig | Dict[str, Any] = "dtam_config.json",
        *,
        auto_listen: bool = True,
        send_workers: int = 4,
    ) -> "DtamClient":
        """Create a client from a short config file or config object."""
        if isinstance(config, DtamNetworkConfig):
            net = config
        elif isinstance(config, dict):
            net = DtamNetworkConfig.from_dict(config)
        else:
            net = load_network_config(config)

        client = cls.module(
            my_ip=net.my.ip,
            my_port=net.my.udp_port,
            my_tcp_port=net.my.tcp_port,
            peer_ip=net.peer.ip,
            peer_port=net.peer.udp_port,
            peer_tcp_port=net.peer.tcp_port,
            auto_listen=auto_listen,
            send_workers=send_workers,
        )
        client.name = net.my.name
        return client

    def __setattr__(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)
        if name in _CALLBACK_NAMES:
            listener = self.__dict__.get("_listener")
            if listener is not None:
                setattr(listener, name, value)

    def __getattr__(self, name: str) -> Any:
        if name in _CALLBACK_NAMES:
            listener = self.__dict__.get("_listener")
            if listener is not None:
                return getattr(listener, name)
        raise AttributeError(name)

    @property
    def base_port(self) -> int:
        return self.my_udp_port

    @property
    def my_port(self) -> int:
        return self.my_udp_port

    @property
    def peer_port(self) -> int:
        return self.peer_udp_port

    @property
    def target_base_port(self) -> int:
        return self.peer_udp_port

    @property
    def listening(self) -> bool:
        return bool(getattr(self._listener, "_running", False))

    def configure(
        self,
        target_ip: str | None = None,
        *,
        base_port: int | None = None,
        udp_port: int | None = None,
        tcp_port: int | None = None,
        target_base_port: int | None = None,
        target_udp_port: int | None = None,
        target_tcp_port: int | None = None,
    ) -> "DtamClient":
        """Update the peer endpoint used by send operations."""
        if target_ip is not None:
            self.peer_ip = target_ip
            self.target_ip = target_ip
        peer_base = target_base_port if target_base_port is not None else base_port
        peer_udp = target_udp_port if target_udp_port is not None else udp_port
        peer_tcp = target_tcp_port if target_tcp_port is not None else tcp_port
        if peer_base is not None or peer_udp is not None or peer_tcp is not None:
            self.peer_udp_port, self.peer_tcp_port = _resolve_ports(
                base_port=peer_base,
                udp_port=peer_udp,
                tcp_port=peer_tcp,
            )
        return self

    set_target = configure
    target = configure
    set_peer = configure

    def set_my_endpoint(
        self,
        *,
        ip: str | None = None,
        port: int | None = None,
        base_port: int | None = None,
        udp_port: int | None = None,
        tcp_port: int | None = None,
    ) -> "DtamClient":
        """Update this module's receive endpoint and restart the listener if needed."""
        if ip is not None:
            self.my_ip = ip
            self.bind_ip = ip
        resolved_base = base_port if base_port is not None else port
        if resolved_base is not None or udp_port is not None or tcp_port is not None:
            self.my_udp_port, self.my_tcp_port = _resolve_ports(
                base_port=resolved_base,
                udp_port=udp_port,
                tcp_port=tcp_port,
            )
            self.udp_port = self.my_udp_port
            self.tcp_port = self.my_tcp_port
        self._replace_listener()
        return self

    def listen(
        self,
        *,
        block: bool = False,
        bind_ip: str | None = None,
        base_port: int | None = None,
        udp_port: int | None = None,
        tcp_port: int | None = None,
    ) -> "DtamClient":
        """Start this module's listener.

        By default this returns immediately and receives in background threads.
        Use ``block=True`` for a simple long-running receiver process.
        """
        needs_replace = (
            bind_ip is not None
            or base_port is not None
            or udp_port is not None
            or tcp_port is not None
        )
        if needs_replace:
            if bind_ip is not None:
                self.my_ip = bind_ip
                self.bind_ip = bind_ip
            self.my_udp_port, self.my_tcp_port = _resolve_ports(
                base_port=base_port,
                udp_port=udp_port,
                tcp_port=tcp_port,
            )
            self.udp_port = self.my_udp_port
            self.tcp_port = self.my_tcp_port
            self._replace_listener()
        if not self.listening:
            self._listener.start(block=block)
        return self

    start = listen
    serve = listen

    def stop(self) -> None:
        self._listener.stop()

    def close(self) -> None:
        if self.listening:
            self.stop()
        self._send_executor.shutdown(wait=False, cancel_futures=True)

    def on(self, message: str | int, callback: Optional[Callback] = None):
        """Register a receive callback by message ID or alias.

        Can be used directly or as a decorator:

            client.on("4001", handle_vehicle_status)

            @client.on("dtam_execute")
            def handle_execute(result):
                ...
        """
        spec = _resolve_message(message)

        def register(cb: Callback) -> Callback:
            setattr(self, spec.callback_name, cb)
            return cb

        if callback is None:
            return register
        return register(callback)

    def off(self, message: str | int) -> None:
        spec = _resolve_message(message)
        setattr(self, spec.callback_name, None)

    def send(
        self,
        message: str | int,
        data: Dict[str, Any],
        *,
        image_bytes: bytes = b"",
        target_ip: str | None = None,
        udp_port: int | None = None,
        tcp_port: int | None = None,
    ) -> PushResult:
        """Validate and send a DTAM message dict."""
        spec = _resolve_message(message)
        ip = target_ip or self.peer_ip
        port = (
            int(tcp_port) if spec.protocol == "tcp" and tcp_port is not None
            else int(udp_port) if spec.protocol == "udp" and udp_port is not None
            else self.peer_tcp_port if spec.protocol == "tcp"
            else self.peer_udp_port
        )
        fn = _sender(spec.sender_name)
        if spec.mid == "4101":
            return fn(data, image_bytes, target_ip=ip, target_port=port)
        return fn(data, target_ip=ip, target_port=port)

    def send_async(
        self,
        message: str | int,
        data: Dict[str, Any],
        *,
        image_bytes: bytes = b"",
        target_ip: str | None = None,
        udp_port: int | None = None,
        tcp_port: int | None = None,
        callback: Optional[SendCallback] = None,
    ) -> Future:
        """Submit a send operation to a background thread and return a Future.

        Use this in simulation/control loops when a failed TCP connection must
        not pause the module. The returned Future eventually contains the same
        ``PushResult`` returned by ``send()``.
        """
        future = self._send_executor.submit(
            self.send,
            message,
            data,
            image_bytes=image_bytes,
            target_ip=target_ip,
            udp_port=udp_port,
            tcp_port=tcp_port,
        )

        def done(fut: Future) -> None:
            try:
                result = fut.result()
            except Exception as exc:
                result = PushResult(target=target_ip or self.peer_ip)
                result.errors.append(f"background send failed: {type(exc).__name__}: {exc}")
            for cb in (callback, self.on_send_result):
                if cb:
                    try:
                        cb(result)
                    except Exception:
                        pass
            if not result and self.on_send_error:
                try:
                    self.on_send_error(result)
                except Exception:
                    pass

        future.add_done_callback(done)
        return future

    def sample(self, message: str | int, **overrides: Any) -> Dict[str, Any]:
        """Return a valid sample payload for a message ID or alias."""
        return sample_payload(message, **overrides)

    def push_sample(
        self,
        message: str | int,
        *,
        image_bytes: bytes | None = None,
        **overrides: Any,
    ) -> PushResult:
        """Send a valid sample payload for a quick integration smoke test."""
        spec = _resolve_message(message)
        data = sample_payload(spec.mid, **overrides)
        if spec.mid == "4101":
            payload = sample_camera_image_bytes() if image_bytes is None else image_bytes
            return self.send(spec.mid, data, image_bytes=payload)
        return self.send(spec.mid, data)

    def push_sample_async(
        self,
        message: str | int,
        *,
        image_bytes: bytes | None = None,
        callback: Optional[SendCallback] = None,
        **overrides: Any,
    ) -> Future:
        spec = _resolve_message(message)
        data = sample_payload(spec.mid, **overrides)
        if spec.mid == "4101":
            payload = sample_camera_image_bytes() if image_bytes is None else image_bytes
            return self.send_async(spec.mid, data, image_bytes=payload, callback=callback)
        return self.send_async(spec.mid, data, callback=callback)

    def push_module_setting_info(self, data: Dict[str, Any], **kwargs: Any) -> PushResult:
        return self.send("0001", data, **kwargs)

    def push_module_setting_info_async(self, data: Dict[str, Any], **kwargs: Any) -> Future:
        return self.send_async("0001", data, **kwargs)

    def push_module_status(self, data: Dict[str, Any], **kwargs: Any) -> PushResult:
        return self.send("0002", data, **kwargs)

    def push_module_status_async(self, data: Dict[str, Any], **kwargs: Any) -> Future:
        return self.send_async("0002", data, **kwargs)

    def push_common_time_info(self, data: Dict[str, Any], **kwargs: Any) -> PushResult:
        return self.send("0003", data, **kwargs)

    def push_common_time_info_async(self, data: Dict[str, Any], **kwargs: Any) -> Future:
        return self.send_async("0003", data, **kwargs)

    def push_sim_mode_setup(self, data: Dict[str, Any], **kwargs: Any) -> PushResult:
        return self.send("1001", data, **kwargs)

    def push_sim_mode_setup_async(self, data: Dict[str, Any], **kwargs: Any) -> Future:
        return self.send_async("1001", data, **kwargs)

    def push_simulation_setup(self, data: Dict[str, Any], **kwargs: Any) -> PushResult:
        return self.send("1002", data, **kwargs)

    def push_simulation_setup_async(self, data: Dict[str, Any], **kwargs: Any) -> Future:
        return self.send_async("1002", data, **kwargs)

    def push_scenario_setup(self, data: Dict[str, Any], **kwargs: Any) -> PushResult:
        return self.send("1003", data, **kwargs)

    def push_scenario_setup_async(self, data: Dict[str, Any], **kwargs: Any) -> Future:
        return self.send_async("1003", data, **kwargs)

    def push_flight_plan_request(self, data: Dict[str, Any], **kwargs: Any) -> PushResult:
        return self.send("2001", data, **kwargs)

    def push_flight_plan_request_async(self, data: Dict[str, Any], **kwargs: Any) -> Future:
        return self.send_async("2001", data, **kwargs)

    def push_dtam_execute(self, data: Dict[str, Any], **kwargs: Any) -> PushResult:
        return self.send("2002", data, **kwargs)

    def push_dtam_execute_async(self, data: Dict[str, Any], **kwargs: Any) -> Future:
        return self.send_async("2002", data, **kwargs)

    def push_scheduled_flight(self, data: Dict[str, Any], **kwargs: Any) -> PushResult:
        return self.send("3001", data, **kwargs)

    def push_scheduled_flight_async(self, data: Dict[str, Any], **kwargs: Any) -> Future:
        return self.send_async("3001", data, **kwargs)

    def push_strategic_separation(self, data: Dict[str, Any], **kwargs: Any) -> PushResult:
        return self.send("3002", data, **kwargs)

    def push_strategic_separation_async(self, data: Dict[str, Any], **kwargs: Any) -> Future:
        return self.send_async("3002", data, **kwargs)

    def push_tactical_separation(self, data: Dict[str, Any], **kwargs: Any) -> PushResult:
        return self.send("3003", data, **kwargs)

    def push_tactical_separation_async(self, data: Dict[str, Any], **kwargs: Any) -> Future:
        return self.send_async("3003", data, **kwargs)

    def push_vehicle_status(self, data: Dict[str, Any], **kwargs: Any) -> PushResult:
        return self.send("4001", data, **kwargs)

    def push_vehicle_status_async(self, data: Dict[str, Any], **kwargs: Any) -> Future:
        return self.send_async("4001", data, **kwargs)

    def push_camera_image(
        self,
        header: Dict[str, Any],
        image_bytes: bytes = b"",
        **kwargs: Any,
    ) -> PushResult:
        return self.send("4101", header, image_bytes=image_bytes, **kwargs)

    def push_camera_image_async(
        self,
        header: Dict[str, Any],
        image_bytes: bytes = b"",
        **kwargs: Any,
    ) -> Future:
        return self.send_async("4101", header, image_bytes=image_bytes, **kwargs)

    def _replace_listener(self) -> None:
        was_running = self.listening
        callbacks = {
            name: self.__dict__.get(name, getattr(self._listener, name, None))
            for name in _CALLBACK_NAMES
        }
        if was_running:
            self._listener.stop()
        self._listener = DtamListener(
            bind_ip=self.my_ip,
            udp_port=self.my_udp_port,
            tcp_port=self.my_tcp_port,
        )
        for name, cb in callbacks.items():
            setattr(self, name, cb)
        if was_running:
            self.listen(block=False)

    def __enter__(self) -> "DtamClient":
        self.listen(block=False)
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


def create_client(target_ip: str | None = None, **kwargs: Any) -> DtamClient:
    return DtamClient(target_ip, **kwargs)
