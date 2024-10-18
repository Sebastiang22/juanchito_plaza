const axios = require('axios');
const { default: makeWASocket, DisconnectReason, useMultiFileAuthState, proto, downloadMediaMessage } = require('@whiskeysockets/baileys');
const log = (pino = require('pino'));
const { Boom } = require('@hapi/boom');
const { writeFile } = require('fs/promises');


// Variables globales
let sock;

// Conectar a WhatsApp
async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('session_auth_info');

    sock = makeWASocket({
        printQRInTerminal: true,
        auth: state,
        logger: log({ level: 'silent' }),
    });

    // Manejar actualizaciones de conexión
    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            // Actualizar QR si es necesario
            console.log('Nuevo QR:', qr);
        }

        if (connection === 'close') {
            const reason = new Boom(lastDisconnect.error).output.statusCode;
            switch (reason) {
                case DisconnectReason.badSession:
                    console.log('Bad Session File, Please Delete and Scan Again');
                    sock.logout();
                    break;
                case DisconnectReason.connectionClosed:
                    console.log('Connection closed, reconnecting...');
                    connectToWhatsApp();
                    break;
                case DisconnectReason.connectionLost:
                    console.log('Connection lost, reconnecting...');
                    connectToWhatsApp();
                    break;
                case DisconnectReason.connectionReplaced:
                    console.log('Connection replaced, another session opened. Close the current session first.');
                    sock.logout();
                    break;
                case DisconnectReason.loggedOut:
                    console.log('Logged out. Delete the session file and scan again.');
                    sock.logout();
                    break;
                case DisconnectReason.restartRequired:
                    console.log('Restart required, restarting...');
                    connectToWhatsApp();
                    break;
                case DisconnectReason.timedOut:
                    console.log('Connection timed out, reconnecting...');
                    connectToWhatsApp();
                    break;
                default:
                    console.log(`Unknown disconnect reason: ${reason} | ${lastDisconnect.error}`);
                    sock.end();
            }
        } else if (connection === 'open') {
            console.log('Connection opened');
        }
    });
    
    // Manejar mensajes entrantes (texto e imagen)
    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        try {
            if (type === 'notify' && messages.length > 0) {
                const message = messages[0];
                const { key, message: msg } = message;
                const { remoteJid } = key;
                const senderNumber = remoteJid.split('@')[0]; // Extraer el número del remitente
                const messageType = Object.keys(msg)[0]; // Tipo de mensaje (texto, imagen, etc.)
    
                let textMessage = '';
                let imageBuffer = null;
    
                if (messageType === 'conversation' || messageType === 'extendedTextMessage') {
                    // Es un mensaje de texto
                    textMessage = msg.conversation || msg.extendedTextMessage?.text;
                    console.log('Número del remitente:', senderNumber);
                    console.log('Mensaje recibido:', textMessage);
                } else if (messageType === 'imageMessage') {
                    // Es un mensaje de imagen
                    textMessage = 'imagen'; // Mensaje predeterminado para imágenes
                    console.log('Número del remitente:', senderNumber);
                    console.log('Imagen recibida');
    
                    try {
                        // obtener la imagen del mensaje
                        imageBuffer = await downloadMediaMessage(message, 'buffer', {}, {
                            // Usar el logger ya inicializado si es necesario
                            reuploadRequest: sock.updateMediaMessage // Para re-subir si es necesario
                        });
                    } catch (error) {
                        console.error('Error al obtener la imagen:', error); // Usar console.error para mejor debug
                        await sock.sendMessage(remoteJid, { text: 'Hubo un error al procesar la imagen.' }, { quoted: message });
                        return;
                    }
                }
    
                // Crear datos del cuerpo de la solicitud POST
                const requestBody = {
                    pregunta: textMessage,
                    celular: senderNumber
                };
    
                if (imageBuffer) {
                    requestBody.imagen = imageBuffer.toString('base64'); // Enviar el buffer como base64
                }
    
                // Enviar una solicitud POST al servidor
                try {
                    const response = await axios.post(
                        'http://chatbot_service_juanchito:8000/chat',
                        requestBody, // Enviar texto e imagen en el cuerpo
                        {
                            headers: {
                                'Content-Type': 'application/json'
                            }
                        }
                    );
                    const responseData = response.data;
    
                    // Responder con la respuesta del servidor, asegurarse que sea un texto
                    await sock.sendMessage(remoteJid, { text: String(responseData) }, { quoted: message });
                    console.log('Respuesta enviada de vuelta:', responseData);
                } catch (error) {
                    console.error('Error en la solicitud POST:', error); // Usar console.error para mejor información
                    await sock.sendMessage(remoteJid, { text: 'Hubo un error al procesar tu solicitud.' }, { quoted: message });
                }
            }
        } catch (error) {
            console.error('Error manejando el mensaje:', error); // Mejor uso de console.error para el logging
        }
    });
    
    

    // Guardar credenciales actualizadas
    sock.ev.on('creds.update', saveCreds);
}

// Función principal para iniciar la conexión
async function main() {
    try {
        await connectToWhatsApp();
    } catch (err) {
        console.log('Error inesperado:', err);
    }
}

// Ejecutar la función principal
main();
