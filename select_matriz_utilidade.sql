SELECT 
    a.id_usuario, 
    a.id_hotel, 
    a.nota,
    h.regiao,
    h.luxo, h.lazer, h.urbano, h.pet_friendly, h.kids_friendly,
    h.acessibilidade, h.seguranca, h.preco, h.silencio, h.capacidade
FROM avaliacoes a
JOIN hoteis h ON a.id_hotel = h.id_hotel;