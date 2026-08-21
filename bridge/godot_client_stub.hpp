// CleanRoomGodotBridge — minimal Unix-socket client stub (Godot 4.x / GDExtension)
// Linux/macOS AF_UNIX. Not for Windows named pipes (use a separate implementation).
// Compile into your Cold Boot extension; link against nothing beyond libc.
//
// network_access: false — do not replace this with TCP.

#pragma once

#include <string>
#include <stdexcept>
#include <cstring>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>

namespace clean_room {

inline std::string unix_request(const std::string& sock_path, const std::string& json_line) {
    int fd = ::socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) throw std::runtime_error("socket() failed");

    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    if (sock_path.size() >= sizeof(addr.sun_path)) {
        ::close(fd);
        throw std::runtime_error("socket path too long");
    }
    std::memcpy(addr.sun_path, sock_path.c_str(), sock_path.size() + 1);

    if (::connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
        ::close(fd);
        throw std::runtime_error("connect() failed");
    }

    std::string out = json_line;
    if (out.empty() || out.back() != '\n') out.push_back('\n');
    if (::write(fd, out.data(), out.size()) < 0) {
        ::close(fd);
        throw std::runtime_error("write() failed");
    }

    std::string resp;
    char buf[4096];
    while (true) {
        ssize_t n = ::read(fd, buf, sizeof(buf));
        if (n < 0) {
            ::close(fd);
            throw std::runtime_error("read() failed");
        }
        if (n == 0) break;
        resp.append(buf, buf + n);
        if (resp.find('\n') != std::string::npos) break;
    }
    ::close(fd);
    auto pos = resp.find('\n');
    if (pos != std::string::npos) resp.resize(pos);
    return resp;
}

}  // namespace clean_room
